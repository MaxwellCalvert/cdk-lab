# cdk-lab
seis616 cdk example app with CLI testing explanation

Log in to AWS CLI, run:
```
cdk synth
cdk deploy --all
```

The first indication that everything is functioning is the Create status returned as the stacks are deployed, but with the assistance of AI I compiled a list of commands that help verify all intended functionality. 
## Verify CREATE_COMPLETE
```
aws cloudformation describe-stacks \
  --stack-name NetworkStack \
  --query 'Stacks[0].StackStatus' \
  --output text

aws cloudformation describe-stacks \
  --stack-name ServerStack \
  --query 'Stacks[0].StackStatus' \
  --output text
```
Should return:
```
CREATE_COMPLETE
CREATE_COMPLETE
```

## Verify Network Stack
```
VPC_ID=$(aws cloudformation describe-stacks \
  --stack-name NetworkStack \
  --query "Stacks[0].Outputs[?OutputKey=='VpcId'].OutputValue" \
  --output text)

aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[*].[SubnetId,AvailabilityZone,CidrBlock,MapPublicIpOnLaunch,Tags[?Key==`Name`].Value|[0]]' \
  --output table
```
Should return:
```
----------------------------------------------------------------------------------------------------------
|                                             DescribeSubnets                                            |
+---------------------------+-------------+--------------+--------+--------------------------------------+
|  subnet-0af874b4eea8b4e3e |  us-east-1b |  10.0.3.0/24 |  False |  NetworkStack/AppVpc/PrivateSubnet2  |
|  subnet-04e9f68eb20e310d7 |  us-east-1a |  10.0.2.0/24 |  False |  NetworkStack/AppVpc/PrivateSubnet1  |
|  subnet-08e4a7a3be3917766 |  us-east-1a |  10.0.0.0/24 |  True  |  NetworkStack/AppVpc/PublicSubnet1   |
|  subnet-06fe977655cef0452 |  us-east-1b |  10.0.1.0/24 |  True  |  NetworkStack/AppVpc/PublicSubnet2   |
+---------------------------+-------------+--------------+--------+--------------------------------------+
```
The subnet ids are not important, but we see that we have 1 public and 1 private subnet in each availability zone
(the False rows are private).

Then we can verify that the private subnets point to a NAT Gateway:

```
aws ec2 describe-route-tables \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'RouteTables[*].[RouteTableId,Tags[?Key==`Name`].Value|[0],Routes[?DestinationCidrBlock==`0.0.0.0/0`].NatGatewayId|[0]]' \
  --output table
```
Which returns:
```
------------------------------------------------------------------------------------------
|                                   DescribeRouteTables                                  |
+-----------------------+--------------------------------------+-------------------------+
|  rtb-09d7e4b0534592c84|  NetworkStack/AppVpc/PublicSubnet2   |  None                   |
|  rtb-05a7976adfa2b7b77|  None                                |  None                   |
|  rtb-0e582bd2b89a4b18e|  NetworkStack/AppVpc/PublicSubnet1   |  None                   |
|  rtb-089045730410da0b3|  NetworkStack/AppVpc/PrivateSubnet2  |  nat-0380b16e813e20d01  |
|  rtb-085e73f33e78672e7|  NetworkStack/AppVpc/PrivateSubnet1  |  nat-0ef6faab4de3075c2  |
+-----------------------+--------------------------------------+-------------------------+
```

## Verify correct security rules
```
aws ec2 describe-security-groups \
  --filters "Name=tag:aws:cloudformation:stack-name,Values=ServerStack" \
  --query 'SecurityGroups[*].[GroupId,GroupName,IpPermissions]' \
  --output json
```
Returns:
```
[
    [
        "sg-0dfaef8bf272eae37",
        "ServerStack-WebServerSG4D0F372C-8iHgk78ZQUpg",
        [
            {
                "IpProtocol": "tcp",
                "FromPort": 80,
                "ToPort": 80,
                "UserIdGroupPairs": [
                    {
                        "Description": "Load balancer to target",
                        "UserId": "637910750805",
                        "GroupId": "sg-0dfaef8bf272eae37"
                    }
                ],
                "IpRanges": [
                    {
                        "Description": "HTTP from anywhere",
                        "CidrIp": "0.0.0.0/0"
                    }
:
[
    [
        "sg-0dfaef8bf272eae37",
        "ServerStack-WebServerSG4D0F372C-8iHgk78ZQUpg",
        [
            {
                "IpProtocol": "tcp",
                "FromPort": 80,
                "ToPort": 80,
                "UserIdGroupPairs": [
                    {
                        "Description": "Load balancer to target",
                        "UserId": "637910750805",
                        "GroupId": "sg-0dfaef8bf272eae37"
                    }
                ],
                "IpRanges": [
                    {
                        "Description": "HTTP from anywhere",
                        "CidrIp": "0.0.0.0/0"
                    } ...
```
## Verify RDS details
```
aws rds describe-db-instances \
  --query 'DBInstances[*].[DBInstanceIdentifier,Engine,DBSubnetGroup.DBSubnetGroupName,PubliclyAccessible,VpcSecurityGroups[*].VpcSecurityGroupId]' \
  --output table
```
Returns:
```
---------------------------------------------------------------
|                     DescribeDBInstances                     |
+-------------------------------------------------------------+
|  serverstack-mysqlinstance216dd474-fbsqbcyhwf2u             |
|  mysql                                                      |
|  serverstack-mysqlinstancesubnetgroupbbb46b1d-ndv3jyerhp6k  |
|  False                                                      |
|  sg-0005eb274bbb34957                                       |
+-------------------------------------------------------------+
```
Here we can verify that the DB Engine is MySQL and that it is not publicly accessible.

## Verify Load Balancer
```
aws elbv2 describe-load-balancers \
  --query 'LoadBalancers[*].[LoadBalancerName,DNSName,Scheme,VpcId]' \
  --output table
```
Returns:
```
---------------------------------------------------------------------------------------------------------------------------------------------
|                                                           DescribeLoadBalancers                                                           |
+---------------------------+------------------------------------------------------------------+------------------+-------------------------+
|  Server-AppAl-vCcAWPYnGS2T|  Server-AppAl-vCcAWPYnGS2T-61031351.us-east-1.elb.amazonaws.com  |  internet-facing |  vpc-099898653254a9c2e  |
+---------------------------+------------------------------------------------------------------+------------------+-------------------------+
```
We can see that the load balancer is internet facing and is in the same VPC we created in the Network Stack.
```
TG_ARN=$(aws elbv2 describe-target-groups \
  --query "TargetGroups[?VpcId=='$VPC_ID'].TargetGroupArn | [0]" \
  --output text)

aws elbv2 describe-target-health \
  --target-group-arn "$TG_ARN" \
  --query 'TargetHealthDescriptions[*].[Target.Id,TargetHealth.State]' \
  --output table
```
Returns:
```
------------------------------------
|       DescribeTargetHealth       |
+----------------------+-----------+
|  i-057cfc72d658e33ca |  healthy  |
|  i-09889370cc83fb4ef |  healthy  |
+----------------------+-----------+
```
This indicates that our targets are healthy. Finally, we can run:
```
curl -s -o /dev/null -w "%{http_code}" http://<ALB-DNS-Name>
```
Replacing the DNS Name with the output from the stack, we should receive a 200 response if the load balancer is working.
