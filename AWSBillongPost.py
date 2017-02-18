#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os,sys,json,datetime
import ConfigParser
import boto3
import slackweb

inifile = ConfigParser.SafeConfigParser()
inifile.read('/home/sprout/.auth_info')

# ==== AWS認証情報 ====
REGION = "us-east-1"
KEY_ID = inifile.get('aws', 'AWS_KEY_ID')
SECRET_KEY = inifile.get('aws', 'AWS_SECRET_KEY')


# ==== AWS認証処理 ====
aws_session = boto3.Session(
                      aws_access_key_id=KEY_ID,
                      aws_secret_access_key=SECRET_KEY,
                      region_name=REGION
                  )
cloudwatch_conn = aws_session.client('cloudwatch')


# ==== Slack認証設定 ====
SLACK_WEBHOOK=inifile.get('slack', 'WEBHOOK_URL')
SLACK_CHANNEL=inifile.get('slack', 'CHANNEL')
SLACK_USER=inifile.get('slack', 'USER')


# ==== 昨日/一昨日の日付を取得する ====
last_date_data = datetime.date.today() -datetime.timedelta(1)
last_date = last_date_data.strftime('%Y/%m/%d')
bef_last_date = (datetime.date.today() -datetime.timedelta(2)).strftime('%Y/%m/%d')


# ==== 関数get_value() ====
# ※ get_value(サービス名)で昨日までのサービス利用料金を取得する
#   サービス名が「ALL」の場合は全体の金額を取得する
def get_value(service_name,check_day):
    if service_name == 'ALL':
        get_demesion = [{'Name': 'Currency', 'Value': 'USD'}]
    else:
        get_demesion = [{'Name': 'ServiceName', 'Value': service },{'Name': 'Currency', 'Value': 'USD'}]

    data = cloudwatch_conn.get_metric_statistics(
           Namespace='AWS/Billing',
           MetricName='EstimatedCharges',
           Period=86400,
           StartTime=check_day + " 00:00:00",
           EndTime=check_day + " 23:59:59",
           Statistics=['Maximum'],
           Dimensions=get_demesion
           )
    for info in data['Datapoints']:
        return info['Maximum']


# ==== AWSのメトリックのサービスリストを取得する ====
# もうちょっと良い書き方が無いものか…
service_list = []
service_value = []
bef_service_value = []
json_value = cloudwatch_conn.list_metrics()
for attr1 in json_value.get('Metrics'):
    for attr2 in attr1.get('Dimensions'):
        if attr2.get('Name') == "ServiceName":
             service_list.append(attr2.get('Value'))
service_list.sort()


# ==== サービス別の金額を取得する ====
for service in service_list:
    service_value.append(get_value(service,last_date))

for service in service_list:
    bef_service_value.append(get_value(service,bef_last_date))

# ==== トータルの金額を取得する ====
last_total_value = get_value('ALL',last_date)
bef_last_total_value = get_value('ALL',bef_last_date)
if last_date_data.day == 1:
    total_before_ratio = last_total_value
else:
    total_before_ratio = last_total_value - bef_last_total_value

# ==== SlackへPostする ====
SLACK_TEXT='昨日までのAWSの利用料金は *$' + str(last_total_value) + '* (前日比 + *$' + str(total_before_ratio) + '* )' + 'になります'

slack=slackweb.Slack(url=SLACK_WEBHOOK)
attachments=[]
attachment={'pretext': '各サービス別の利用料金','fields': []}

for var in range(0, len(service_list)):
    if last_date_data.day == 1:
      before_ratio=service_value[var]
    else:
      before_ratio=service_value[var] - bef_service_value[var]
    item={'title': service_list[var] ,'value': ' $' + str(service_value[var]) + ' (前日比 +$' + str(before_ratio) + ') ' ,'short': "true"}
    attachment['fields'].append(item)

attachments.append(attachment)
slack.notify(text=SLACK_TEXT, channel=SLACK_CHANNEL, username=SLACK_USER, icon_emoji=":aws-icon:", attachments=attachments)