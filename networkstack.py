from aws_cdk import Stack, aws_ec2 as ec2, CfnOutput
from constructs import Construct

class NetworkStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.vpc = ec2.Vpc(
            self, "AppVpc",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,  # Distribute across two availability zones
            nat_gateways=2,  # One NAT Gateway per AZ (high availability), can be reduced to 1 for cost savings in lab environments
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        # Export VPC ID for use by ServerStack
        CfnOutput(self, "VpcId", value=self.vpc.vpc_id, export_name="NetworkVpcId")