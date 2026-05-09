# FlightFlux Infrastructure

AWS infrastructure for the FlightFlux project, provisioned with AWS CDK (TypeScript).
All resources live in `us-east-1` under a single CloudFormation stack: `FlightFluxStack`.

---

## Live Endpoints

| Resource | Value |
|----------|-------|
| Kafka bootstrap servers | `b-2.flightfluxkafka.o5ttlt.c11.kafka.us-east-1.amazonaws.com:9092,b-1.flightfluxkafka.o5ttlt.c11.kafka.us-east-1.amazonaws.com:9092` |
| Redis host | `flightflux-redis.d5ozwo.0001.use1.cache.amazonaws.com:6379` |
| MongoDB URI | `mongodb://10.0.2.193:27017/flightdelay` |
| EMR Cluster ID | `j-6KXFO0VO5SBI` |
| API server (public) | `32.193.196.179:8000` |
| Dashboard server (public) | `52.200.95.87:8501` |

All values are also in `.env` in this directory.

> **Note:** Redis and MongoDB are on private VPC IPs. They are only reachable from within
> the VPC — i.e. from the EC2 instances, not from your laptop.

---

## Infrastructure Overview

### Networking
- VPC `flightflux-vpc` — `10.0.0.0/16`, 2 AZs
- 2 public subnets (API + Dashboard EC2)
- 2 private subnets (MongoDB, MSK brokers, Redis, EMR)
- 1 NAT Gateway for private subnet egress (e.g. OpenSky API calls)
- Security group `flightflux-sg` — internal ports 9092, 27017, 6379, 8000, 8501; SSH on 22

### S3 Buckets
| Bucket | Purpose |
|--------|---------|
| `flightdelay-raw` | Raw BTS CSVs and OpenSky JSON |
| `flightdelay-processed` | Parquet files partitioned by `year=/month=` |
| `flightdelay-models` | Serialized Spark MLlib pipeline artifacts (versioning enabled) |

All buckets have public access blocked.

### MSK (Kafka)
- Cluster: `flightflux-kafka`, Kafka 3.6, 2 brokers (`kafka.t3.small`)
- Topics:
  - `flights-raw` — 3 partitions, replication factor 1
  - `flights-enriched` — 3 partitions, replication factor 1

### ElastiCache (Redis)
- Cluster: `flightflux-redis`, Redis 7.1, `cache.t3.micro`
- Used as a live cache for recent flight predictions

### MongoDB
- EC2 `t3.medium` in private subnet, MongoDB 7 Community
- Database: `flightdelay`
- Collections: `flights_enriched`, `airports`

### EMR (Spark)
- Cluster: `flightflux-emr`, EMR 7.0, Spark
- Primary + Core: `m5.xlarge` × 1 each
- **Auto-terminates after 1 hour idle** (see section below)

### EC2 App Servers
- `flightflux-api` — `t3.small`, public subnet, Elastic IP `32.193.196.179`
- `flightflux-dashboard` — `t3.small`, public subnet, Elastic IP `52.200.95.87`

---

## Accessing Resources

### SSH into EC2 instances
```bash
ssh -i flightflux-key.pem ec2-user@32.193.196.179   # API server
ssh -i flightflux-key.pem ec2-user@52.200.95.87     # Dashboard server
```

If you don't have the `.pem` file, use **EC2 Instance Connect** in the AWS console:
EC2 → Instances → select instance → Connect → EC2 Instance Connect → Connect.

### MongoDB
Connect from within the VPC (e.g. from the API EC2 instance):
```bash
mongosh "mongodb://10.0.2.193:27017/flightdelay"
```

### Redis
Connect from within the VPC:
```bash
redis-cli -h flightflux-redis.d5ozwo.0001.use1.cache.amazonaws.com -p 6379
```

### Kafka
Run from within the VPC (e.g. API EC2 instance) using the Kafka CLI:
```bash
# List topics
bin/kafka-topics.sh --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS --list

# Consume from flights-raw (for debugging)
bin/kafka-console-consumer.sh \
  --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS \
  --topic flights-raw --from-beginning
```

### S3
```bash
aws s3 ls s3://flightdelay-raw/
aws s3 ls s3://flightdelay-processed/
aws s3 ls s3://flightdelay-models/
```

### EMR — submit a Spark job
```bash
aws emr add-steps \
  --cluster-id j-6KXFO0VO5SBI \
  --steps Type=Spark,Name="MyJob",ActionOnFailure=CONTINUE,\
Args=[--deploy-mode,cluster,--class,Main,s3://flightdelay-raw/jobs/myjob.py] 
```

---

## EMR Auto-Termination

EMR is configured to **automatically shut down after 1 hour of idle time** (no active Spark jobs running). This saves cost — an idle EMR cluster costs ~$0.40/hour.

### When EMR will terminate
- No Spark jobs have been submitted for 60 minutes
- The cluster moves to `TERMINATING` → `TERMINATED` state

### When to spin EMR up
Only start EMR when you need to run a Spark job:
- Batch ingestion (CSV → Parquet)
- ML training (Spark MLlib)
- Stream processing (Spark Structured Streaming)

### EMR does NOT restart itself
Once terminated, you must manually bring it back. Two ways:

**Option A — CDK redeploy (recommended)**
```bash
cd infra
npx cdk deploy 
```
CDK detects the cluster is gone and recreates it. Takes ~10 min.
Update `EMR_CLUSTER_ID` in `.env` with the new cluster ID from the output.

**Option B — AWS CLI (faster, one-off)**
```bash
aws emr create-cluster \
  --name flightflux-emr \
  --release-label emr-7.0.0 \
  --applications Name=Spark \
  --instance-groups \
    InstanceGroupType=MASTER,InstanceType=m5.xlarge,InstanceCount=1 \
    InstanceGroupType=CORE,InstanceType=m5.xlarge,InstanceCount=1 \
  --service-role flightflux-emr-role \
  --ec2-attributes InstanceProfile=flightflux-emr-ec2-profile \
  --auto-termination-policy IdleTimeout=3600 \
  
```
Update `EMR_CLUSTER_ID` in `.env` with the new cluster ID printed in the output.

---

## Teardown

Destroys all resources including EC2, MSK, Redis, EMR, and S3 buckets (buckets are emptied automatically).

```bash
cd infra
npx cdk destroy 
```

Type `y` when prompted. Takes ~10 minutes.

> MSK can take an extra 5-10 min to fully delete. If the destroy hangs, check the
> CloudFormation console for the `FlightFluxStack` stack status.

---

## Bring Everything Back Up

```bash
cd infra
npm install          # only needed if node_modules is missing
npx cdk deploy 
```

After deploy:
1. Note the new endpoint values printed in the outputs
2. Update `.env` with any changed values (Elastic IPs are persistent, but EMR cluster ID will be new)
3. Recreate Kafka topics if MSK was destroyed (see below)

### Recreating Kafka topics after a full teardown
SSH into the API instance and run:
```bash
cd kafka_2.13-3.6.0

bin/kafka-topics.sh --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS \
  --create --topic flights-raw --partitions 3 --replication-factor 1

bin/kafka-topics.sh --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS \
  --create --topic flights-enriched --partitions 3 --replication-factor 1
```

---

## CDK Stack Structure

```
infra/
├── bin/app.ts                  # CDK app entry point
├── lib/flightflux-stack.ts     # All resources in one stack
├── cdk.json
├── package.json
├── tsconfig.json
├── .env                        # Live endpoint values
└── README.md
```
