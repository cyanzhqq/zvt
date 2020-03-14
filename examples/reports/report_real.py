# -*- coding: utf-8 -*-
import logging
import time
from typing import List

import eastmoneypy
from apscheduler.schedulers.background import BackgroundScheduler

from examples.factors.block_selector import BlockSelector
from examples.reports import get_subscriber_emails
from zvt import init_log
from zvt.domain import Stock1dKdata, BlockStock
from zvt.factors.ma.ma_factor import VolumeUpMa250Factor
from zvt.factors.target_selector import TargetSelector
from zvt.informer.informer import EmailInformer

logger = logging.getLogger(__name__)

sched = BackgroundScheduler()


@sched.scheduled_job('cron', hour=17, minute=30, day_of_week='mon-fri')
def report_real():
    while True:
        error_count = 0
        email_action = EmailInformer()

        try:
            # 抓取k线数据
            # StockTradeDay.record_data(provider='joinquant')
            # Stock1dKdata.record_data(provider='joinquant')

            latest_day: Stock1dKdata = Stock1dKdata.query_data(order=Stock1dKdata.timestamp.desc(), limit=1,
                                                               return_type='domain')
            target_date = latest_day[0].timestamp

            # 计算均线
            my_selector = TargetSelector(start_timestamp='2018-01-01', end_timestamp=target_date)
            # add the factors
            factor1 = VolumeUpMa250Factor(start_timestamp='2018-01-01', end_timestamp=target_date)

            my_selector.add_filter_factor(factor1)

            my_selector.run()

            long_targets = my_selector.get_open_long_targets(timestamp=target_date)
            if long_targets:
                # use block to filter
                block_selector = BlockSelector(start_timestamp='2020-01-01')
                block_selector.run()
                long_blocks = block_selector.get_open_long_targets(timestamp=target_date)
                block_stocks: List[BlockStock] = BlockStock.query_data(provider='sina',
                                                                       filters=[BlockStock.stock_id.in_(long_targets)],
                                                                       entity_ids=long_blocks, return_type='domain')
                # add them to eastmoney
                try:
                    try:
                        eastmoneypy.del_group('real')
                    except:
                        pass
                    eastmoneypy.create_group('real')
                    for stock in block_stocks:
                        eastmoneypy.add_to_group(stock.stock_code, group_name='real')
                except Exception as e:
                    email_action.send_message("5533061@qq.com", f'report_real error',
                                              'report_real error:{}'.format(e))

                info = [f'{stock.stock_name}({stock.stock_code})' for stock in block_stocks]
                msg = ' '.join(info)
            else:
                msg = 'no targets'

            logger.info(msg)

            email_action.send_message(get_subscriber_emails(), f'{target_date} 放量突破年线real选股结果', msg)

            break
        except Exception as e:
            logger.exception('report_real error:{}'.format(e))
            time.sleep(60 * 3)
            error_count = error_count + 1
            if error_count == 10:
                email_action.send_message("5533061@qq.com", f'report_real error',
                                          'report_real error:{}'.format(e))


if __name__ == '__main__':
    init_log('report_real.log')

    report_real()

    sched.start()

    sched._thread.join()