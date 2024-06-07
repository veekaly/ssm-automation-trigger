import boto3, botocore, logging
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger()
logger.setLevel("INFO")

s3 = boto3.client("s3")

def list_bundles_latest(bucket, instance, time_delta):
    start_from = datetime.now(pytz.utc) - timedelta(minutes=time_delta)
    try:
        bundles = list()
        response = s3.list_objects_v2(
            Bucket=bucket,
            Prefix=f'eks_{instance}'
        )
        if response.get('Contents'):
            bundles = [{"key": content['Key'], "timestamp": content['LastModified']} for content in response['Contents'] if content['LastModified'] >= start_from]
    except botocore.exceptions.ClientError as error:
        logger.error(error)
        raise error
    else:
        return bundles

