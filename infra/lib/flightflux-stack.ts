import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as msk from 'aws-cdk-lib/aws-msk';
import * as elasticache from 'aws-cdk-lib/aws-elasticache';
import * as emr from 'aws-cdk-lib/aws-emr';
import * as budgets from 'aws-cdk-lib/aws-budgets';
import { Construct } from 'constructs';

export class FlightFluxStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ─── Networking ───────────────────────────────────────────────────────────────

    const vpc = new ec2.Vpc(this, 'Vpc', {
      vpcName: 'flightflux-vpc',
      maxAzs: 2,
      natGateways: 1,
      subnetConfiguration: [
        { name: 'Public', subnetType: ec2.SubnetType.PUBLIC, cidrMask: 24 },
        { name: 'Private', subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS, cidrMask: 24 },
      ],
    });

    const sg = new ec2.SecurityGroup(this, 'SecurityGroup', {
      vpc,
      securityGroupName: 'flightflux-sg',
      description: 'FlightFlux internal services',
      allowAllOutbound: true,
    });

    // Internal service ports
    sg.addIngressRule(ec2.Peer.ipv4(vpc.vpcCidrBlock), ec2.Port.tcp(9092), 'Kafka');
    sg.addIngressRule(ec2.Peer.ipv4(vpc.vpcCidrBlock), ec2.Port.tcp(27017), 'MongoDB');
    sg.addIngressRule(ec2.Peer.ipv4(vpc.vpcCidrBlock), ec2.Port.tcp(6379), 'Redis');
    sg.addIngressRule(ec2.Peer.ipv4(vpc.vpcCidrBlock), ec2.Port.tcp(8000), 'FastAPI');
    sg.addIngressRule(ec2.Peer.ipv4(vpc.vpcCidrBlock), ec2.Port.tcp(8501), 'Streamlit');
    sg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(22), 'SSH');

    // ─── S3 Buckets ──────────────────────────────────────────────────────────────

    const rawBucket = new s3.Bucket(this, 'RawBucket', {
      bucketName: 'flightdelay-raw',
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const processedBucket = new s3.Bucket(this, 'ProcessedBucket', {
      bucketName: 'flightdelay-processed',
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const modelsBucket = new s3.Bucket(this, 'ModelsBucket', {
      bucketName: 'flightdelay-models',
      versioned: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // ─── IAM ─────────────────────────────────────────────────────────────────────

    const emrServiceRole = new iam.Role(this, 'EmrServiceRole', {
      roleName: 'flightflux-emr-role',
      assumedBy: new iam.ServicePrincipal('elasticmapreduce.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonElasticMapReduceRole'),
      ],
    });

    const emrEc2Role = new iam.Role(this, 'EmrEc2Role', {
      roleName: 'flightflux-emr-ec2-role',
      assumedBy: new iam.ServicePrincipal('ec2.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonElasticMapReduceforEC2Role'),
      ],
    });

    // Grant EMR EC2 role access to all three buckets
    rawBucket.grantReadWrite(emrEc2Role);
    processedBucket.grantReadWrite(emrEc2Role);
    modelsBucket.grantReadWrite(emrEc2Role);

    const emrEc2InstanceProfile = new iam.CfnInstanceProfile(this, 'EmrEc2Profile', {
      instanceProfileName: 'flightflux-emr-ec2-profile',
      roles: [emrEc2Role.roleName],
    });

    const ec2AppRole = new iam.Role(this, 'Ec2AppRole', {
      roleName: 'flightflux-ec2-role',
      assumedBy: new iam.ServicePrincipal('ec2.amazonaws.com'),
    });
    modelsBucket.grantRead(ec2AppRole);

    // ─── MSK (Kafka) ─────────────────────────────────────────────────────────────

    const kafkaCluster = new msk.CfnCluster(this, 'KafkaCluster', {
      clusterName: 'flightflux-kafka',
      kafkaVersion: '3.6.0',
      numberOfBrokerNodes: 2,
      brokerNodeGroupInfo: {
        instanceType: 'kafka.t3.small',
        clientSubnets: vpc.selectSubnets({ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }).subnetIds,
        securityGroups: [sg.securityGroupId],
        storageInfo: { ebsStorageInfo: { volumeSize: 50 } },
      },
      encryptionInfo: {
        encryptionInTransit: { clientBroker: 'TLS_PLAINTEXT', inCluster: false },
      },
    });

    // ─── ElastiCache (Redis) ─────────────────────────────────────────────────────

    const redisSubnetGroup = new elasticache.CfnSubnetGroup(this, 'RedisSubnetGroup', {
      description: 'FlightFlux Redis subnets',
      cacheSubnetGroupName: 'flightflux-redis-subnets',
      subnetIds: vpc.selectSubnets({ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }).subnetIds,
    });

    const redisCluster = new elasticache.CfnCacheCluster(this, 'RedisCluster', {
      clusterName: 'flightflux-redis',
      engine: 'redis',
      engineVersion: '7.1',
      cacheNodeType: 'cache.t3.micro',
      numCacheNodes: 1,
      cacheSubnetGroupName: redisSubnetGroup.ref,
      vpcSecurityGroupIds: [sg.securityGroupId],
    });
    redisCluster.addDependency(redisSubnetGroup);

    // ─── EMR (Spark) ─────────────────────────────────────────────────────────────

    const emrCluster = new emr.CfnCluster(this, 'EmrCluster', {
      name: 'flightflux-emr',
      releaseLabel: 'emr-7.0.0',
      applications: [{ name: 'Spark' }],
      serviceRole: emrServiceRole.roleArn,
      jobFlowRole: emrEc2InstanceProfile.ref,
      instances: {
        ec2SubnetId: vpc.selectSubnets({ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }).subnetIds[0],
        additionalMasterSecurityGroups: [sg.securityGroupId],
        additionalSlaveSecurityGroups: [sg.securityGroupId],
        masterInstanceGroup: { instanceCount: 1, instanceType: 'm5.xlarge', market: 'ON_DEMAND', name: 'Primary' },
        coreInstanceGroup: { instanceCount: 1, instanceType: 'm5.xlarge', market: 'ON_DEMAND', name: 'Core' },
      },
      autoTerminationPolicy: { idleTimeout: 3600 },
      visibleToAllUsers: true,
      bootstrapActions: [{
        name: 'install-python-deps',
        scriptBootstrapAction: {
          path: `s3://${rawBucket.bucketName}/bootstrap/emr-bootstrap.sh`,
        },
      }],
    });

    // ─── EC2 — MongoDB (Private) ─────────────────────────────────────────────────

    const mongoInstance = new ec2.Instance(this, 'MongoDBInstance', {
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
      machineImage: ec2.MachineImage.latestAmazonLinux2023(),
      securityGroup: sg,
      instanceName: 'flightflux-mongodb',
    });

    mongoInstance.addUserData(
      'cat <<\'EOF\' > /etc/yum.repos.d/mongodb-org-7.0.repo',
      '[mongodb-org-7.0]',
      'name=MongoDB Repository',
      'baseurl=https://repo.mongodb.org/yum/amazon/2023/mongodb-org/7.0/x86_64/',
      'gpgcheck=1',
      'enabled=1',
      'gpgkey=https://pgp.mongodb.com/server-7.0.asc',
      'EOF',
      'dnf install -y mongodb-org',
      "sed -i 's/bindIp: 127.0.0.1/bindIp: 0.0.0.0/' /etc/mongod.conf",
      'systemctl enable mongod',
      'systemctl start mongod',
      'sleep 5',
      'mongosh --eval \'db = db.getSiblingDB("flightdelay"); db.createCollection("flights_enriched"); db.createCollection("airports");\'',
    );

    // ─── EC2 — API & Dashboard (Public) ──────────────────────────────────────────

    const apiInstance = new ec2.Instance(this, 'ApiInstance', {
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.SMALL),
      machineImage: ec2.MachineImage.latestAmazonLinux2023(),
      securityGroup: sg,
      role: ec2AppRole,
      instanceName: 'flightflux-api',
    });
    apiInstance.addUserData(
      'dnf install -y python3.11 python3.11-pip git',
      'python3.11 -m pip install fastapi uvicorn boto3 pymongo redis',
    );

    const dashInstance = new ec2.Instance(this, 'DashboardInstance', {
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.SMALL),
      machineImage: ec2.MachineImage.latestAmazonLinux2023(),
      securityGroup: sg,
      role: ec2AppRole,
      instanceName: 'flightflux-dashboard',
    });
    dashInstance.addUserData(
      'dnf install -y python3.11 python3.11-pip git',
      'python3.11 -m pip install streamlit boto3 pymongo redis pandas plotly',
    );

    // Elastic IPs for public instances
    new ec2.CfnEIP(this, 'ApiEip', { instanceId: apiInstance.instanceId });
    new ec2.CfnEIP(this, 'DashEip', { instanceId: dashInstance.instanceId });

    // ─── Billing alerts ──────────────────────────────────────────────────────────

    // BILLING_ALERT_EMAIL is sourced from env at synth time so we don't bake
    // a personal address into the public repo. Set it before `cdk deploy`:
    //   PowerShell: $env:BILLING_ALERT_EMAIL = "your@email"
    //   bash:       export BILLING_ALERT_EMAIL=your@email
    const billingEmail = process.env.BILLING_ALERT_EMAIL;
    if (billingEmail) {
      [50, 100, 200].forEach((threshold) => {
        new budgets.CfnBudget(this, `BudgetAlert${threshold}`, {
          budget: {
            budgetType: 'COST',
            timeUnit: 'MONTHLY',
            budgetName: `flightflux-monthly-${threshold}USD`,
            budgetLimit: { amount: threshold, unit: 'USD' },
          },
          notificationsWithSubscribers: [
            {
              notification: {
                notificationType: 'ACTUAL',
                comparisonOperator: 'GREATER_THAN',
                threshold: 100,
                thresholdType: 'PERCENTAGE',
              },
              subscribers: [{ subscriptionType: 'EMAIL', address: billingEmail }],
            },
            {
              notification: {
                notificationType: 'FORECASTED',
                comparisonOperator: 'GREATER_THAN',
                threshold: 100,
                thresholdType: 'PERCENTAGE',
              },
              subscribers: [{ subscriptionType: 'EMAIL', address: billingEmail }],
            },
          ],
        });
      });
    } else {
      cdk.Annotations.of(this).addWarning(
        'BILLING_ALERT_EMAIL not set — skipping budget resources. ' +
        'Set the env var before `cdk deploy` to enable cost alerts at $50, $100, $200.',
      );
    }

    // ─── Outputs ─────────────────────────────────────────────────────────────────

    new cdk.CfnOutput(this, 'KafkaClusterArn', { value: kafkaCluster.ref, description: 'MSK Cluster ARN — use AWS CLI to get bootstrap brokers' });
    new cdk.CfnOutput(this, 'RedisEndpoint', { value: redisCluster.attrRedisEndpointAddress, description: 'REDIS_HOST' });
    new cdk.CfnOutput(this, 'EmrClusterId', { value: emrCluster.ref, description: 'EMR_CLUSTER_ID' });
    new cdk.CfnOutput(this, 'MongoDBPrivateIp', { value: mongoInstance.instancePrivateIp, description: 'MONGODB_URI host' });
    new cdk.CfnOutput(this, 'ApiPublicIp', { value: apiInstance.instancePublicIp, description: 'FastAPI public IP' });
    new cdk.CfnOutput(this, 'DashboardPublicIp', { value: dashInstance.instancePublicIp, description: 'Streamlit public IP' });
  }
}
