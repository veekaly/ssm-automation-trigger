import boto3, botocore, logging

logger = logging.getLogger()
logger.setLevel("INFO")

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