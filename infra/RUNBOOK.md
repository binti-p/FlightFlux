# FlightFlux Infrastructure Runbook

Operational procedures for the FlightFlux AWS stack. For a description of
*what* the stack contains, see [`infra/README.md`](README.md). This
document is for *what to do when something goes wrong*.

All commands assume:
- AWS CLI configured (`aws sts get-caller-identity` works)
- You are inside `infra/` for any `cdk` command
- Live endpoint values are sourced from [`infra/.env`](.env)

## Where things live

| Resource | Quick check |
|----------|-------------|
| MSK Kafka | AWS console → MSK → `flightflux-kafka` |
| Redis | AWS console → ElastiCache → `flightflux-redis` |
| EMR | AWS console → EMR → `flightflux-emr` (cluster ID `j-…` in `.env`) |
| MongoDB | EC2 instance `flightflux-mongodb` (private subnet) |
| API EC2 | `flightflux-api`, public IP in `.env` |
| Dashboard EC2 | `flightflux-dashboard`, public IP in `.env` |
| S3 | `flightdelay-raw`, `flightdelay-processed`, `flightdelay-models` |

## Common incidents

### EMR cluster is gone

EMR auto-terminates after 60 min of idle. Symptom: `aws emr describe-cluster --cluster-id $EMR_CLUSTER_ID` returns `TERMINATED` or `does not exist`.

**Fix:** redeploy via CDK (recreates everything that's missing):

```bash
cd infra
npx cdk deploy
```

Update `EMR_CLUSTER_ID` in [`infra/.env`](.env) with the new ID printed
in the stack outputs.

### Kafka topics missing after teardown

CDK provisions the MSK cluster but does NOT create topics — they must be
recreated manually after a full teardown.

SSH into the API instance (it has the Kafka CLI installed) and run:

```bash
cd kafka_2.13-3.6.0

bin/kafka-topics.sh --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS \
  --create --topic flights-raw --partitions 3 --replication-factor 1

bin/kafka-topics.sh --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS \
  --create --topic flights-enriched --partitions 3 --replication-factor 1
```

Verify:

```bash
bin/kafka-topics.sh --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS --list
```

### Streaming job is silent (no flights in Redis)

In order, check:

1. **Poller alive?** SSH to the API instance, `ps aux | grep opensky_client`. If dead, restart `python streaming/poller/opensky_client.py`.
2. **Messages reaching Kafka?**
   ```bash
   bin/kafka-console-consumer.sh \
     --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS \
     --topic flights-raw --from-beginning --max-messages 5
   ```
3. **Spark job alive?** Check the EMR Steps tab in the AWS console. If terminated, resubmit the job (see "Submit a Spark job" below).
4. **Redis writes succeeding?** From inside the VPC: `redis-cli -h flightflux-redis.d5ozwo.0001.use1.cache.amazonaws.com keys "flight:*" | head`.

### MongoDB unreachable

MongoDB is on a private VPC IP — only reachable from inside the VPC. From
the API instance:

```bash
mongosh "mongodb://10.0.2.193:27017/flightdelay" --eval "db.adminCommand('ping')"
```

If the EC2 instance was stopped/restarted, MongoDB should auto-start
because `systemctl enable mongod` is in user-data. If it didn't, SSH in
and `sudo systemctl start mongod`.

### S3 access denied from EMR

The EMR EC2 role (`flightflux-emr-ec2-role`) has read/write on all three
buckets. If access fails:

1. Confirm the cluster was launched with `--ec2-attributes InstanceProfile=flightflux-emr-ec2-profile` (check EMR console → Security & access).
2. Confirm bucket names in the job match `flightdelay-raw|processed|models`.

## Routine operations

### Submit a Spark job to EMR

```bash
aws emr add-steps \
  --cluster-id "$EMR_CLUSTER_ID" \
  --steps Type=Spark,Name="csv-to-parquet",ActionOnFailure=CONTINUE,Args=[--deploy-mode,cluster,s3://flightdelay-raw/jobs/csv_to_parquet.py,--input,s3://flightdelay-raw/bts/,--output,s3://flightdelay-processed/]
```

Watch progress: `aws emr describe-step --cluster-id $EMR_CLUSTER_ID --step-id <step-id>`.

### Tail Spark logs

```bash
aws emr ssh --cluster-id "$EMR_CLUSTER_ID" --key-pair-file flightflux-key.pem
yarn logs -applicationId <appId>
```

### Redeploy after a config change

```bash
cd infra
npm install            # only if node_modules is missing
npx cdk diff           # preview changes
npx cdk deploy
```

After deploy, reconcile any changed values in [`infra/.env`](.env) — Elastic IPs persist, but EMR cluster ID and MSK bootstrap brokers will be new if those resources were recreated.

### Full teardown

```bash
cd infra
npx cdk destroy
```

Type `y` when prompted. ~10 minutes; MSK can take an extra 5–10 min to
fully delete. If the destroy hangs, check the CloudFormation console for
the `FlightFluxStack` stack status.

## Cost guardrails

EMR and MSK are the expensive components. Idle EMR is ~$0.40/hour; the
`autoTerminationPolicy` set in the CDK stack kills it after 1h idle.

If the team is not actively running jobs, run `npx cdk destroy` overnight
to drop everything except S3 (buckets remain but raw/processed Parquet
incurs negligible cost).

> **TODO:** Add CloudWatch billing alarms at $50 / $100 / $200 to the
> CDK stack (see Wk2 Thu-Fri P1 deliverable in the dev plan).

## Useful AWS CLI one-liners

```bash
# Live endpoint values
aws elasticache describe-cache-clusters --cache-cluster-id flightflux-redis \
  --show-cache-node-info --query 'CacheClusters[0].CacheNodes[0].Endpoint'

aws kafka list-clusters --query 'ClusterInfoList[?ClusterName==`flightflux-kafka`].ClusterArn' --output text

aws emr list-clusters --active --query 'Clusters[?Name==`flightflux-emr`].Id' --output text

# S3 sanity
aws s3 ls s3://flightdelay-processed/ --recursive --summarize | tail
```
