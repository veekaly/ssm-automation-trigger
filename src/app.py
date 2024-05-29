import json, logging
from lib.ec2 import get_instance_id
from lib.kubernetes import KubeAPI

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
