#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { FlightFluxStack } from '../lib/flightflux-stack';

const app = new cdk.App();

new FlightFluxStack(app, 'FlightFluxStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION ?? 'us-east-1',
  },
});
