import urllib.request
import json
import time
import traceback

_zmetrics_obj = None

URI_TAG_INTERNAL = "i"
URI_TAG_EXTERNAL = "c"
URI_TAG_SERVER = "s"


def _TraceBack():
    errMsg = ''
    errss = traceback.format_exc().split('\n')
    for ers in errss:
        errMsg = errMsg + str(ers)
    return errMsg


def InitMetricsModel(app_name, service_name, version, logger, protocol="HTTP"):
    """

    Function: InitMetricsModel

    Summary: InsertHere

    Examples: InsertHere

    Attributes:

        @param (app_name):InsertHere

        @param (service_name):InsertHere

        @param (version):InsertHere

        @param (logger):InsertHere

        @param (protocol) default="HTTP": InsertHere

    Returns: InsertHere

    """
    global _zmetrics_obj
    _zmetrics_obj = Metrics(app_name, service_name, version, logger, protocol)
    logger.info("===== InitMetricsModel ========")
    return _zmetrics_obj


class Metrics(object):
    """upload request status to metrics"""

    def __init__(self, app_name, service_name, version, logger, protocol=None):
        self._appName = app_name
        self._serviceName = service_name
        self._version = version
        self._logger = logger
        self._URL = "http://127.0.0.1:10039/metrics_api"
        if protocol is None:
            self._protocol = "HTTP"
        else:
            self._protocol = protocol
        self._scale = [0, 10, 50, 100,
                       200, 300, 500, 1000, 2000, 5000,
                       10000, 30000, 60000, 120000,
                       300000, 600000, 1800000, 3600000,
                       18000000]
        for i in range(len(self._scale)):
            self._scale[i] = 1000 * self._scale[i]

    def post_data(self, uri=None, uri_tag=None,
                  res_code=None, duration=None, is_success="n"):
        if (uri is None or
            uri_tag is None or
            res_code is None or
                duration is None):
            self._logger.error('missing param in metrics function:post_data, uri=%s', str(uri))
            return

        values = {
            "ver": "0.1",
            "server_id": 0,
            "idc_id": 0,
            "isp": "",
            "app_name": self._appName,
            "app_ver": "1.0",
            "service_name": self._serviceName,
            "service_ver": self._version,
            "protocol": self._protocol,
            "defmodel": [{
                "topic": "",
                "uri": uri,
                "uri_tag": uri_tag,
                "duration": int(duration) * 1000,
                "code": res_code,
                "isSuccess": is_success,
                "scale": self._scale
            }]
        }
        resp = None
        try:
            jdata = json.dumps(values)
            # resp = urllib.request.urlopen(url=self._URL, data=jdata.encode(), timeout=2)
            # r = resp.read()
            # self._logger.debug("report response: %s", r)
        except Exception as e:
            print('post data to metrics fail!  Exception=%s'%str(e))
            self._logger.error(e)
        finally:
            if resp:
                resp.close()


def METRICS(uri_tag="i", parent_uri=""):
    """

    Function: METRICS

    Summary: InsertHere

    Examples: InsertHere

    Attributes:

        @param (uri_tag) default="i": InsertHere

        @param (parent_uri) default="": InsertHere

    Returns: InsertHere

    """

    global _zmetrics_obj

    def wraperout(cb):
        uri = cb.__name__
        if parent_uri != "":
            uri = "%s/%s" % (parent_uri, uri)

        def wraper(*argv, **kwargv):
            start_time = time.time()
            rst = None
            try:
                rst = cb(*argv, **kwargv)
            except:
                _zmetrics_obj._logger.error(_TraceBack())
                print(_TraceBack())
            if rst is None or len(rst) < 2 or rst[1] not in [True, False]:
                _zmetrics_obj._logger.error(
                    'The Function response is not '
                    'match \METRICS protocol. URI:%r  rst:%s',
                    uri, str(rst))
                return rst
            code = rst[0]
            isSuccess = rst[1]
            if isSuccess:
                isSuccess = 'y'
            else:
                isSuccess = 'n'
            elapsed_time = (time.time() - start_time) * 1000
            _zmetrics_obj.post_data(uri=uri, uri_tag=uri_tag,
                                    res_code=code, duration=elapsed_time,
                                    is_success=isSuccess)
            rst2 = rst[2:]
            if len(rst2) == 1:
                rst2 = rst2[0]

            return rst2
        return wraper
    return wraperout
