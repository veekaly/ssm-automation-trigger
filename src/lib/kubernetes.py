from kubernetes import client, config
import boto3, botocore
import base64
from botocore.signers import RequestSigner
import logging, re

logger = logging.getLogger()
logger.setLevel("DEBUG")

class KubeAPI:
    def __init__(self, cluster_name, region):
        self.cluster_name = cluster_name
        self.region = region
        kubeconfig = self._get_kubeconfig(cluster_name, region)
        config.load_kube_config_from_dict(config_dict=kubeconfig)
        self.core_v1 = client.CoreV1Api()

    def _get_bearer_token(self):
        STS_TOKEN_EXPIRES_IN = 60
        session = boto3.session.Session()

        client = session.client('sts', region_name=self.region)
        service_id = client.meta.service_model.service_id

        signer = RequestSigner(
            service_id,
            self.region,
            'sts',
            'v4',
            session.get_credentials(),
            session.events
        )

        params = {
            'method': 'GET',
            'url': 'https://sts.{}.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15'.format(self.region),
            'body': {},
            'headers': {
                'x-k8s-aws-id': self.cluster_name
            },
            'context': {}
        }

        signed_url = signer.generate_presigned_url(
            params,
            region_name=self.region,
            expires_in=STS_TOKEN_EXPIRES_IN,
            operation_name=''
        )

        base64_url = base64.urlsafe_b64encode(signed_url.encode('utf-8')).decode('utf-8')

        # remove any base64 encoding padding:
        return 'k8s-aws-v1.' + re.sub(r'=*', '', base64_url)

    def _get_kubeconfig(self, cluster_name, region):
        try:
            eks = boto3.client("eks", region_name=region)
            cluster = eks.describe_cluster(name=cluster_name)
            token = self._get_bearer_token()
            cluster_config = {
                "apiVersion": "v1",
                "clusters": [{
                    "name": cluster_name,
                    "cluster": {
                        "certificate-authority-data": cluster["cluster"]["certificateAuthority"]["data"],
                        "server": cluster["cluster"]["endpoint"]
                    }
                }],
                "contexts": [{"name": cluster["cluster"]["arn"], "context": {"cluster": cluster_name, "user": "aws"}}],
                "current-context": cluster["cluster"]["arn"],
                "kind": "Config",
                "preferences": {},
                "users": [{"name": "aws", "user" : {"token": token}}]
            }
        except botocore.exceptions.ClientError as error:
            logger.error(error)
        else:
            return cluster_config

    def get_node_info(self, node):
        try:
            node_info = self.core_v1.read_node(name=node)
            node_status = node_info.status.conditions[-1].type
            node_addresses = node_info.status.addresses
        except client.exceptions.ApiException as error:
            logger.error(f"Error getting node information: {error}")
        else:
            return {
                "node": node,
                "node_status": node_status,
                "node_addresses": node_addresses
            }
    



