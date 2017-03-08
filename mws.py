# coding: utf-8

import socks
import socket
import urllib.parse
import urllib.request

import xml.etree.ElementTree as ET

import hmac
import time
import cchardet as chardet

from hashlib import sha256
from base64 import b64encode

MARKETPLACES = {
    "CA" : ("https://mws.amazonservices.ca", "A2EUQ1WTGCTBG2"),
    "US" : ("https://mws.amazonservices.com", "ATVPDKIKX0DER"), 
    "DE" : ("https://mws-eu.amazonservices.com", "A1PA6795UKMFR9"),
    "ES" : ("https://mws-eu.amazonservices.com", "A1RKKUPIHCS9HS"),
    "FR" : ("https://mws-eu.amazonservices.com", "A13V1IB3VIYZZH"),
    "IN" : ("https://mws.amazonservices.in", "A21TJRUUN4KGV"),
    "IT" : ("https://mws-eu.amazonservices.com", "APJ6JRA9NG5V4"),
    "UK" : ("https://mws-eu.amazonservices.com", "A1F83G8C2ARO7P"),
    "JP" : ("https://mws.amazonservices.jp", "A1VC38T7YXB528"),
    "CN" : ("https://mws.amazonservices.com.cn", "AAHKV2X7AFYLW"),
    "MX" : ("https://mws.amazonservices.com.mx", "A1AM78C64UM0Y8")
}

class MWSError(Exception):
    pass

# ベースクラス
class BaseObject(object):

    _response = None

    _namespace = {
        "ns": "http://mws.amazonaws.com/doc/2009-01-01/"
    }

    VERSION = "2009-01-01"

    def __init__(self, AWSAccessKeyId=None, AWSSecretAccessKey=None,
            SellerId=None, Region='US', Version="", MWSAuthToken="", Port=None):

        self.AWSAccessKeyId     = AWSAccessKeyId
        self.AWSSecretAccessKey = AWSSecretAccessKey
        self.SellerId = SellerId
        self.Region   = Region
        self.Version  = Version or self.VERSION
        self.Port     = Port

        if Region in MARKETPLACES:
            self.service_domain = MARKETPLACES[self.Region][0]
        else:
            raise MWSError("Incorrrect region supplied {region}".format(**{"region": region}))

    # APIを叩く
    def request(self, method="POST", **kwargs):
        params = {
            "AWSAccessKeyId": self.AWSAccessKeyId,
            "Merchant": self.SellerId,
            "SignatureVersion": 2,
            "Timestamp": self.timestamp,
            "Version": self.Version,
            "SignatureMethod": "HmacSHA256"
        }

        params.update(kwargs)

        signature, query_string = self.signature(method, params)

        url = self.build_url(query_string, signature)

        if self.Port is not None:
            socks.set_default_proxy(socks.SOCKS5, "localhost", self.Port)
            socket.socket = socks.socksocket
       
        request = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(request) as page:
            self._response = page.read()
        return self

    def signature(self, method, params):
        query_string = self.quote_query(params)

        data = method + "\n" + self.service_domain.replace("https://", "") + "\n/\n" + query_string

        if type(self.AWSSecretAccessKey) is str:
            self.AWSSecretAccessKey = self.AWSSecretAccessKey.encode('utf-8')

        if type(data) is str:
            data = data.encode('utf-8')

        digest = hmac.new(self.AWSSecretAccessKey, data, sha256).digest()
        return (urllib.parse.quote(b64encode(digest)), query_string)

    def build_url(self, query_string, signature):
        return "%s/?%s&Signature=%s" % (self.service_domain, query_string, signature)

    @staticmethod
    def quote_query(query):
        return "&".join("%s=%s" % (
            k, urllib.parse.quote(
                str(query[k]).encode('utf-8'), safe='-_.~'))
                for k in sorted(query))

    @property
    def timestamp(self):
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # 生のレスポンスデータ
    @property
    def raw(self):
        return self._response

    # レスポンスデータのxmlをパース
    @property
    def parse(self):
        if self._response is None:
            raise
        return ET.fromstring(self._response)

    def find(self, element):
        return self.parse.find(".//ns:%s" % element, self._namespace)

# レポート取得関連のクラス
class Report(BaseObject):

    # レポート生成をリクエストする
    def request_report(self, ReportType=None):
        return self.request(**{"Action": "RequestReport", "ReportType": ReportType, "MarketplaceIdList.Id.1": MARKETPLACES[self.Region][1]})

    # レポート生成リクエスト一覧取得
    def get_report_request_list(self, RequestId=None):
        return self.request(**{"Action": "GetReportRequestList", "ReportRequestIdList.Id.1": RequestId})

    # レポート一覧を取得
    def get_report_list(self, RequestId=None):
        return self.request(**{"Action": "GetReportList", "ReportRequestIdList.Id.1": RequestId})

    # レポートを取得
    def get_report(self, ReportId=None):
        return self.request(**{"Action": "GetReport", "ReportId": ReportId})

if __name__ == "__main__":

    SellerID           = "SellerId"
    AWSAccesKeyId      = "AWSAccessKeyId"
    AWSSecretAccessKey = "AWSSecretAccessKey"

    report = Report(
        AWSAccessKeyId=AWSAccessKeyId,
        AWSSecretAccessKey=AWSSecretAccessKey,
        SellerId=SellerId)

    # 出品商品レポートの生成をリクエスト
    response = report.request_report(ReportType="_GET_MERCHANT_LISTINGS_DATA_")
    # リクエストIDを取得
    request_id = response.find("ReportRequestId").text

    # レポートが完成してレポートIDが取得できるまで監視する
    while True:
        # リクエストIDからレポートの生成状況を取得する
        response = report.get_report_request_list(RequestId=request_id)
        # statusが_DONE_がどうか確認。_DONE_だったらレポートIDを取得して終了
        if "_DONE_" == response.find("ReportProcessingStatus").text:
            report_id = response.find("GeneratedReportId").text
            break 
        # 頻繁にアクセスすると503エラーなどが返ってくる場合があるので2分間スリープする
        time.sleep(120)
    
    try:
        # 取得したレポートIDをもとにレポートを取得する
        response = report.get_report(ReportId=report_id)
        print(response.raw) 
    except Exception as e:
        print(e)
