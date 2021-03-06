#!/usr/bin/python
# -*- coding=utf-8 -*-


__author__ = ['"wuyadong" <wuyadong311521@gmail.com>']

import datetime
import logging
import traceback
import hashlib
import tornado.web
import operation
import config
import database
import util


class BaseHandler(tornado.web.RequestHandler):
    """定义公共函数
    """

    def get_error_html(self, status_code, **kwargs):
        reason = "Server Error" if not hasattr(self, "_reason") else self._reason
        exception = kwargs.get('exception', "")

        return self.render_string("error.html", code=str(status_code),
                                  reason=str(reason), exception=str(exception))


class OperationHandler(BaseHandler):
    """clean data
    """

    def get(self, *args, **kwargs):
        secret = self.get_argument("secret", "")
        m = hashlib.md5()
        m.update(secret)
        if m.hexdigest() != config.secret:
            self.set_status(403)
            self.write('{"code": 403, "msg": "secret wrong"}')
        else:
            path = self.request.path
            if path not in operation.operation_route.get_operation_routes():
                self.set_status(404)
                self.write('{"code": 404, "msg": "no operation"}')
            else:
                method = operation.operation_route.get_operation_routes()[path]
                try:
                    method(self.request.arguments)
                except Exception as e:
                    import traceback
                    stack = traceback.format_exc()
                    logging.error("operation error:%s\n%s" % (e, stack))
                    self.set_status(500)
                    self.write('{"code": 500, "msg": "%s"}' % str(e))
                else:
                    self.set_status(200)
                    self.write('{"code": 200, "msg": "success"}')


class DayHandler(BaseHandler):
    """用于获取某一天的新闻
    """
    def __init__(self, application, request, **kwargs):
        super(DayHandler, self).__init__(application, request, **kwargs)

    def get(self, *args, **kwargs):
        default_date_str = datetime.datetime.now().strftime("%Y%m%d")
        date_str = self.get_argument("date", default_date_str)

        news_list = _get_news(date_str)

        after_date = None if date_str == default_date_str \
            else util.after_date_str(date_str)

        # empty
        if len(news_list) == 0 and date_str == default_date_str:
            date_str = util.before_date_str(default_date_str)
            news_list = _get_news(date_str)
            after_date = None

        self.render("day.html", now_date=util.now_date_str(),
                    before_date=util.before_date_str(date_str),
                    after_date=after_date,
                    news_list=news_list)


@util.cached(expiration=60*30)
def _get_news(date_str):
    news_list = []
    dao = database.Dao()
    try:
        newses = dao.select_news_list(date_str)
        if newses:
            for news in newses:
                news_list.append(dict(share_url=news[3],
                                      image_public_url=news[8],
                                      image_source=news[7],
                                      title=news[2]))
        return news_list
    finally:
        dao.close()


class SearchHandler(BaseHandler):
    """处理搜索
    """
    def __init__(self, application, request, **kwargs):
        super(SearchHandler, self).__init__(application, request, **kwargs)

    def get(self, *args, **kwargs):
        keywords = self.get_argument("keywords", "")
        if not keywords.strip():
            self.redirect("/")
            return

        hits = _search(keywords)
        self.render("search.html", hits=hits, keywords=keywords)


def _search(keywords):
    import search
    hits = []
    fts_searcher = search.FTSSearcher()
    results = fts_searcher.search(keywords, limit=10)

    db = database.Dao()
    try:
        for hit in results:
            try:
                news = db.get_news(hit['news_id'])
                text = util.extract_text(news[5])
                summary = hit.highlights('content', text=text, top=2)
                hits.append(dict(
                    image_public_url=news[8],
                    share_url=news[3],
                    date=news[4],
                    title=news[2],
                    summary=summary,
                ))
            except Exception, e:
                stack = traceback.format_exc()
                logging.error("one hit error: %s\n%s" % (e, stack))
    finally:
        db.close()
        fts_searcher.close()

    return hits


class ErrorHandler(BaseHandler):
    """处理错误信息
    """

    def prepare(self):
        self.render("404.html")