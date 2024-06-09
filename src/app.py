import json, logging, os
from lib.ec2 import get_instances
from lib.ssm import start_execution
from lib.kubernetes import KubeAPI
from lib.s3 import list_bundles_latest

logger = logging.getLogger()
logger.setLevel("INFO")

CLUSTER_ID=os.environ['CLUSTER_ID']
CLUSTER_REGION=os.environ['CLUSTER_REGION']
BUNDLE_SLEEP_DURATION=int(os.environ['BUNDLE_SLEEP_DURATION'])
NODE_RATE_LIMIT=int(os.environ['NODE_RATE_LIMIT'])
LOG_COLLECTION_BUCKET=os.environ['LOG_COLLECTION_BUCKET']
SSM_AUTOMATION_EXECUTION_ROLE_ARN=os.environ['SSM_AUTOMATION_EXECUTION_ROLE_ARN']

def lambda_handler(event, context):
    try:
        for record in event['Records']:
            message = json.loads(record['Sns']['Message'])
            logger.info(message)
            alerts = message['alerts']
 
        for alert in alerts:
            if alert['labels']['alertname'] == 'KubeNNR':
                nnr_execution(alert['labels']['node'])
            elif alert['labels']['alertname'] == 'KubeNNRGT5':
                logger.info(f"The EKS cluster {CLUSTER_ID} in region {CLUSTER_REGION} has more than 3 nodes in Not Ready state")
                kubeapi = KubeAPI(CLUSTER_ID, CLUSTER_REGION)
                not_ready_nodes = kubeapi.list_nodes_notready(NODE_RATE_LIMIT)
                nnr_gt_execution(not_ready_nodes)
            else:
                logger.error("Invalid alert received, skipping.")
    except Exception as error:
        logger.error(error)

def nnr_execution(node):
    try:
        instances = get_instances([node])
        for instance in instances:
            start_execution(instance, LOG_COLLECTION_BUCKET, SSM_AUTOMATION_EXECUTION_ROLE_ARN)
    except Exception as error:
        raise error
    
def nnr_gt_execution(nodes):
    try:
        not_ready_instances = get_instances(nodes)
        logger.info(f"Found {len(not_ready_instances)} instances in Not Ready state: {', '.join(not_ready_instances)}")
        for instance in not_ready_instances:
            bundles = list_bundles_latest(LOG_COLLECTION_BUCKET, instance, BUNDLE_SLEEP_DURATION)
            if len(bundles) > 0:
                logger.info(f"Bundle for instance {instance} already uploaded in last {BUNDLE_SLEEP_DURATION} mins, skipping.")
            else:
                start_execution(instance, LOG_COLLECTION_BUCKET, SSM_AUTOMATION_EXECUTION_ROLE_ARN)
    except Exception as error:
        raise error