# SSM Automation Trigger [Under Construction]

SSM Automation trigger receives alerts from EKS cluster(s) and executes the appropriate SSM automation to analyze/remediate issues.

## Architecture
![architecture](./files/architecture.png)

## Setup Instructions

1. Create an EKS Cluster
```
export CLUSTER_NAME=ssm-automation-trigger
export REGION=us-east-1
export AWS_ACCOUNT_ID=1234567890
eksctl create cluster --name ${CLUSTER_NAME} --region ${REGION}
```

2. Create an IRSA role for the alertmanager pod to perform AWS actions
```
cat <<EOF > alertmanager-sns-policy.json
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

aws iam create-policy --policy-name AlertManagerSNSPolicy --policy-document file://alertmanager-sns-policy.json --region ${REGION}

rm alertmanager-sns-policy.json
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

3. Deploy the kube-prometheus-stack helm chart
```
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack -n prometheus --values ./prometheus/kube-prometheus-stack-values.yaml
```

4. Deploy AWS SAM template to create the Lambda function, SNS Topic, and related components
```
sam build --use-container
sam deploy --guided
```

5. Test the lambda code locally
```
sam local invoke --event events/sns.json
```

6. Configure alertmanager to send alert notifications to Amazon SNS
```
export SNS_TOPIC_ARN=<topic-arn-from-sam-deploy-output>
```
```
cat <<EOF > prometheus/alertmanagerconfig.yaml
---
apiVersion: monitoring.coreos.com/v1alpha1
kind: AlertmanagerConfig
metadata:
  name: sns-receiver
  namespace: prometheus
  labels:
    alertmanagerConfig: sns-receiver
spec:
  route:
    groupBy: ['job']
    groupWait: 30s
    groupInterval: 5m
    repeatInterval: 5m
    receiver: 'amazon-sns'
    routes:
    - receiver: 'amazon-sns'
      matchers:
      - name: "alertname"
        value: "KubeNodeNotReady"
        matchType: "="
  receivers:
  - name: 'amazon-sns'
    snsConfigs:
    - sigv4:
        region: ${REGION}
      topicARN: ${SNS_TOPIC_ARN}
      subject: alertmanager
EOF
```
```
kubectl apply -f prometheus/alertmanagerconfig.yaml
```

