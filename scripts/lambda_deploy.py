import boto3

client = boto3.client('lambda')

def push_function(function_name, image_uri):
    response = client.update_function_code(
        FunctionName=function_name,
        ImageUri=image_uri,
    )
    print(response)