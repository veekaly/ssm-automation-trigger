import json, boto3, botocore
import logging

logger = logging.getLogger()
logger.setLevel("INFO")

def lambda_handler(event, context):
    try:
        for record in event['Records']:
            message = json.loads(record['Sns']['Message'])
            alerts = message['alerts']
            filtered_alerts = filter_alerts(alerts, "KubeNodeNotReady")
            logger.info(filtered_alerts)
    except Exception as error:
        logger.error(error)


def filter_alerts(alerts, labelname):
    filtered_alerts = list()
    for alert in alerts:
        if alert['labels']['alertname'] == labelname:
            filtered_alerts.append(alert)
    return filtered_alerts

def get_instance_id(node_list):
    try:
        ec2 = boto3.client("ec2")
        response = ec2.describe_instances(
            Filters=[
                {
                    'Name': 'private-dns-name',
                    'Values': node_list
                }
            ]
        )
        instance_ids = list()
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_ids.append(instance['InstanceId'])
    except botocore.exceptions.ClientError as error:
        logger.error(error)
    else:
        return instance_ids
