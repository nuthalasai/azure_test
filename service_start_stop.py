import boto3
import datetime
import json

def lambda_handler(event, context):
    # Load the input parameters from DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('ecs-start-stop')
    override_table = dynamodb.Table('Environment')
    rds_table = dynamodb.Table('rds-start-stop')


    override_response = override_table.scan()
    print(f'override_response: {override_response} ')
    override_items = override_response['Items']
    print(f'override_items: {override_items} ')

    override_dict = {}
    for override_item in override_items:
        override_dict[override_item['Environment']] = int(override_item['override_keep_live'])
    print(f'override dict: {override_dict}')

    response = table.scan()
    print(f'response: {response}')
    items = response['Items']
    print(f'items: {items}')

    rds_response = rds_table.scan()
    print(f'rds_response: {rds_response}')
    rds_items = rds_response['Items']
    print(f'rds_items: {rds_items}')

    # Get the current day of the week (0 = Monday, 6 = Sunday)
    day_of_week = datetime.datetime.today().weekday()

    # Update the ECS desired count based on the specified day of the week
    for item in items:
        start_day = int(item['start_day'])
        stop_day = int(item['stop_day'])
        environment = item['Environment']
        service = item['service']
        cluster = item['cluster']
        keep_live = int(item['keep_live'])

        if environment in override_dict and override_dict[environment] != -1:
            keep_live = override_dict[environment]

        if day_of_week == stop_day:
            if keep_live <= 0:
                ecs_client = boto3.client('ecs')
                response = ecs_client.update_service(
                    cluster=cluster,
                    service=service,
                    desiredCount=0
                )
                print(f'Stopped ECS service: {environment} {cluster} {service}')
            else:
                print(f'Skipped stopping ECS service: {environment} {cluster} {service} due to keep_live count')
        elif day_of_week == start_day:
            ecs_client = boto3.client('ecs')
            response = ecs_client.update_service(
                cluster=cluster,
                service=service,
                desiredCount=1
            )
            print(f'Started ECS service: {environment} {cluster} {service}')

# Update the RDS status based on the specified day of the week
    for item in rds_items:
        start_day = int(item['start_day'])
        stop_day = int(item['stop_day'])
        environment = item['Environment']
        db_instance_id = item['db_instance_id']
        keep_live = int(item['keep_live'])

        if environment in override_dict and override_dict[environment] != -1:
            keep_live = override_dict[environment]

        rds_client = boto3.client('rds')
        db_instance = rds_client.describe_db_instances(DBInstanceIdentifier=db_instance_id)['DBInstances'][0]

        if day_of_week == stop_day:
            if keep_live <= 0:
                if db_instance['DBInstanceStatus'] == 'available':
                    response = rds_client.stop_db_instance(DBInstanceIdentifier=db_instance_id)
                    print(f'Stopped RDS instance: {environment} {db_instance_id}')
                else:
                    print(f'Skipped stopping RDS instance: {environment} {db_instance_id} as it is already {db_instance["DBInstanceStatus"]}')
            else:
                print(f'Skipped stopping RDS instance: {environment} {db_instance_id} due to keep_live count')
        elif day_of_week == start_day:
            if db_instance['DBInstanceStatus'] == 'stopped':
                response = rds_client.start_db_instance(DBInstanceIdentifier=db_instance_id)
                print(f'Started RDS instance: {environment} {db_instance_id}')
            else:
                print(f'Skipped starting RDS instance: {environment} {db_instance_id} as it is already {db_instance["DBInstanceStatus"]}')
