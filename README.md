# SSM Automation Trigger [Under Construction]

SSM Automation trigger receives alerts from EKS cluster(s) and executes the appropriate SSM automation to analyze/remediate issues.

## Architecture
![architecture](./files/architecture.png)

## Setup Instructions

1. Deploy AWS SAM template to create the S3 Bucket, Lambda function, SNS Topic, and related components
```
sam build --use-container
sam deploy --guided
```
```
# Set the SNS Topic created in the above step as an environment variable
export SNS_TOPIC_ARN=<topic-arn-from-sam-deploy-output>
export LOG_COLLECTION_BUCKET=<LogCollectionS3Bucket-arn-from-sam-deploy-output>
export LAMBDA_EXECUTION_IAM_ROLE_ARN=<iam-role-arn-of-SSMTriggerFunctionIAMRole-from-sam-deploy-output>
```

2. Create an EKS Cluster
```
export CLUSTER_NAME=ssm-automation-trigger
export REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity | jq -r '.Account')
eksctl create cluster --name ${CLUSTER_NAME} --region ${REGION}
```

3. Create an IAM Policy and attach it to EKS nodegroup IAM Role(s) for log bundle upload permissions
```
cat <<EOF > /tmp/s3-log-upload-policy.json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetBucketAcl",
                "s3:GetBucketPolicyStatus"
            ],
            "Resource": "$LOG_COLLECTION_BUCKET"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject"
            ],
            "Resource": "$LOG_COLLECTION_BUCKET/eks_i-*"
        }
    ]
}
EOF

aws iam create-policy --policy-name SSMAutomationEKSLogCollector --policy-document file:///tmp/s3-log-upload-policy.json

NODEGROUP_ROLE_NAME=$(eksctl get nodegroups --cluster $CLUSTER_NAME --region $REGION -o json | jq -r '.[0].NodeInstanceRoleARN' | cut -d'/' -f2)

aws iam attach-role-policy --role-name $NODEGROUP_ROLE_NAME --policy-arn arn:aws:iam::$AWS_ACCOUNT_ID:policy/SSMAutomationEKSLogCollector
```

3. Create an IRSA role for the alertmanager pod to perform AWS actions
```
cat <<EOF > /tmp/alertmanager-sns-policy.json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "sns:Publish"
            ],
            "Resource":"*"
        }
    ]
}
EOF

aws iam create-policy --policy-name AlertManagerSNSPolicy --policy-document file:///tmp/alertmanager-sns-policy.json --region ${REGION}
```

```
eksctl utils associate-iam-oidc-provider --region=${REGION} --cluster=${CLUSTER_NAME} --approve
```

```
eksctl create iamserviceaccount \
    --cluster=${CLUSTER_NAME} \
    --namespace=prometheus \
    --name=alertmanager \
    --role-name AlertManagerSNSRole \
    --attach-policy-arn=arn:aws:iam::${AWS_ACCOUNT_ID}:policy/AlertManagerSNSPolicy \
    --region=${REGION} \
    --approve
```

4. Deploy the kube-prometheus-stack helm chart
```
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
sed "s/TOPIC_ARN/$SNS_TOPIC_ARN/g; s/REGION/$REGION/g" prometheus/kube-prometheus-stack-values.yaml.tmp > prometheus/kube-prometheus-stack-values.yaml
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack -n prometheus --values ./prometheus/kube-prometheus-stack-values.yaml
```

5. Provide EKS read-only access to the Lambda IAM Role

```
kubectl create clusterrole nodeviewer --verb=get,list,watch --resource=nodes

aws eks create-access-entry --cluster-name ${CLUSTER_NAME} \
    --principal-arn ${LAMBDA_EXECUTION_IAM_ROLE_ARN} \
    --username ssm-automation-trigger
    --kubernetes-groups nodeviewer
```

6. Test the lambda code locally
```
# For testing individual node not-ready workflow
sam local invoke --event events/kube-not-ready.json
```
```
# For testing 5 or more nodes in not-ready workflow
sam local invoke --event events/kube-not-ready-gt-5.json
```