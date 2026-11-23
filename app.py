import aws_cdk as cdk
from networkstack import NetworkStack
from serverstack import ServerStack

app = cdk.App()
env = cdk.Environment(account='637910750805', region='us-east-1')
network = NetworkStack(app, "NetworkStack", env=env)
ServerStack(app, "ServerStack", vpc=network.vpc,env=env)
app.synth()