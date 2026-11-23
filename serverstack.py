from aws_cdk import (
    Stack, aws_ec2 as ec2, aws_rds as rds,
    aws_elasticloadbalancingv2 as elbv2,
    aws_autoscaling as autoscaling, CfnOutput, Duration
)
from constructs import Construct

class ServerStack(Stack):
    def __init__(self, scope: Construct, id: str, vpc: ec2.IVpc, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ---------- Security Groups ----------
        web_sg = ec2.SecurityGroup(
            self, "WebServerSG",
            vpc=vpc,
            description="Allow HTTP from anywhere",
            allow_all_outbound=True,
        )
        web_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP from anywhere")

        rds_sg = ec2.SecurityGroup(
            self, "RdsSG",
            vpc=vpc,
            description="Allow MySQL only from WebServers",
        )
        # Key: Use connections API to automatically reference web_sg, avoiding circular dependency
        rds_sg.connections.allow_from(web_sg, ec2.Port.tcp(3306), "MySQL from WebServers")

        # ---------- RDS (MySQL, placed in private subnets) ----------
        rds.DatabaseInstance(
            self, "MySQLInstance",
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_8_0
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[rds_sg],
            database_name="appdb",
            credentials=rds.Credentials.from_generated_secret("admin"),
            removal_policy=None,  # Set as needed
        )

        # ---------- Web Servers (ASG or two individual instances) ----------
        # Use AutoScalingGroup to ensure instances are distributed across public subnets in multiple AZs
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "yum update -y",
            "yum install -y httpd",
            "systemctl start httpd",
            "systemctl enable httpd",
            "echo '<h1>Hello from CDK</h1>' > /var/www/html/index.html",
        )

        asg = autoscaling.AutoScalingGroup(
            self, "WebAsg",
            vpc=vpc,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE2, ec2.InstanceSize.MICRO
            ),
            machine_image=ec2.AmazonLinuxImage(
                generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
            ),
            user_data=user_data,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=web_sg,
            desired_capacity=2,
            min_capacity=2,
            max_capacity=4,
        )

        # ---------- ALB ----------
        alb = elbv2.ApplicationLoadBalancer(
            self, "AppAlb",
            vpc=vpc,
            internet_facing=True,
            security_group=web_sg,  # Reuse Web SG, port 80 already open
        )

        listener = alb.add_listener("HttpListener", port=80, open=True)
        listener.add_targets("WebTargets", port=80, targets=[asg])

        CfnOutput(self, "AlbDns", value=alb.load_balancer_dns_name)