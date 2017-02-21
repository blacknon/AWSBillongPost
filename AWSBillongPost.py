#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os,sys,json,datetime
import ConfigParser
import boto3
import slackweb

iniFile = ConfigParser.SafeConfigParser()
iniFile.read('/opt/script/.auth_info')

# ==== AWS認証情報 ====
region      = "us-east-1"
keyID       = iniFile.get('aws', 'AWS_KEY_ID')
secretKeyID = iniFile.get('aws', 'AWS_SECRET_KEY')


# ==== Slack認証設定 ====
slackWebhook = iniFile.get('slack', 'WEBHOOK_URL')
slackChannel = iniFile.get('slack', 'CHANNEL')
slackUser    = iniFile.get('slack', 'USER')


# ==== AWS認証処理 ====
awsSession = boto3.Session(
                      aws_access_key_id     = keyID,
                      aws_secret_access_key = secretKeyID,
                      region_name           = region
                  )
cloudwatchConn = awsSession.client('cloudwatch')


# ==== 昨日/一昨日の日付を取得する ====
lastDay = datetime.date.today() -datetime.timedelta(1)
lastDayStr = lastDay.strftime('%Y/%m/%d')
befLastDayStr = (datetime.date.today() -datetime.timedelta(2)).strftime('%Y/%m/%d')


# ==== リストの宣言 ====
serviceNameList     = []
serviceValueList    = []
befServiceValueList = []


# ==== 関数getValue() ====
# ※ get_value(サービス名)で昨日までのサービス利用料金を取得する
#   サービス名が「ALL」の場合は全体の金額を取得する
def getValue(sName,checkDay):
    if sName == 'ALL':
        getDemesion = [{'Name': 'Currency', 'Value': 'USD'}]
    else:
        getDemesion = [{'Name': 'ServiceName', 'Value': sName },{'Name': 'Currency', 'Value': 'USD'}]
    data = cloudwatchConn.get_metric_statistics(
           Namespace  = 'AWS/Billing',
           MetricName = 'EstimatedCharges',
           Period     = 86400,
           StartTime  = checkDay + " 00:00:00",
           EndTime    = checkDay + " 23:59:59",
           Statistics = ['Maximum'],
           Dimensions = getDemesion
           )
    for info in data['Datapoints']:
          return info['Maximum']


def getListServiceValue(checkServiceList,checkDay):
    returnValueList = []
    for sName in checkServiceList:
        sValue = getValue(sName,checkDay)
        if sValue is None:
            sValue =0
        returnValueList.append(sValue)
    return returnValueList


# ==== AWSのメトリックのサービスリストを取得する ====
# もうちょっと良い書き方が無いものか…
jsonValue = cloudwatchConn.list_metrics()
for attr1 in jsonValue.get('Metrics'):
    for attr2 in attr1.get('Dimensions'):
        if attr2.get('Name') == "ServiceName":
             serviceNameList.append(attr2.get('Value'))
serviceNameList.sort()


# ==== サービス別の金額を取得する ====
serviceValueList    = getListServiceValue(serviceNameList,lastDayStr)
befServiceValueList = getListServiceValue(serviceNameList,befLastDayStr)


# ==== トータルの金額を取得する ====
lastDayTotalValue    = getValue('ALL',lastDayStr)
befLastDayTotalValue = getValue('ALL',befLastDayStr)

if lastDay.day == 1:
    ratioTotal = lastDayTotalValue
else:
    ratioTotal = lastDayTotalValue - befLastDayTotalValue

# ==== SlackへPostするデータの作成 ====
slactText   = '昨日までのAWSの利用料金は *$' + str(lastDayTotalValue) + '* (前日比 + *$' + str(ratioTotal) + '* )' + 'になります'

slack       = slackweb.Slack(url=slackWebhook)
attachments = []
attachment  = {'pretext': '各サービス別の利用料金','fields': []}

for var in range(0, len(serviceNameList)):
    if lastDay.day == 1:
        serviceRatio = serviceValueList[var]
    else:
        serviceRatio = serviceValueList[var] - befServiceValueList[var]
    item={'title': serviceNameList[var] ,
          'value': ' $' + str(serviceValueList[var]) + ' (前日比 +$' + str(serviceRatio) + ') ' ,
          'short': "true"}
    attachment['fields'].append(item)

attachments.append(attachment)
slack.notify( text       = slactText,
              channel    = slackChannel,
              username   = slackUser,
              icon_emoji = ":aws-icon:",
              attachments=attachments
            )
