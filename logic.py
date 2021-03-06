# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback
import time
import threading
import platform
# third-party

# sjva 공용
from framework import app, db, scheduler, path_app_root, path_data
from framework.job import Job
from framework.util import Util

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting
from .logic_gsheet import LogicGSheet
#########################################################

class Logic(object):
    db_default = { 
        'db_version' : '1',
        'path_credentials' : os.path.join(path_data, package_name, 'credentials.json'),
        'path_accounts' : os.path.join(path_data, package_name, 'accounts'),
        'path_token' : os.path.join(path_data, package_name, 'token.pickle'),
        'gclone_path' : os.path.join(os.path.dirname(__file__), 'bin', 'gclone'),
        'gclone_config_path' : os.path.join(path_data, package_name, 'gclone.conf'),
        'gclone_queue_list' : '',
        'gclone_fix_option' : '--log-level INFO --stats 1s',
        'gclone_user_option' : '--drive-server-side-across-configs --tpslimit 3 --transfers 3 --create-empty-src-dirs --ignore-existing --size-only --disable ListR',
        'gclone_default_folderid' : '',
        # added by orial for gsheet
        'gsheet_auto_start': 'False',
        'gsheet_interval': '60',
        'use_user_setting': 'True',
        'category_rules': u'영화/국내\n드라마/국내',
        'keyword_rules': u'',
        'except_keyword_rules': u'',
        'except_category_rules': u'',
        'user_copy_dest_rules': u'',
        'copy_delay_use':'False',
        'copy_delay':'30',
        'copy_count_limit':'1',
        'copy_mode':'0',
        'plex_condition':'0',   # 미사용
    }

    @staticmethod
    def db_init():
        try:
            for key, value in Logic.db_default.items():
                if db.session.query(ModelSetting).filter_by(key=key).count() == 0:
                    db.session.add(ModelSetting(key, value))
            db.session.commit()
            Logic.migration()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def plugin_load():
        try:
            logger.debug('%s plugin_load', package_name)
            Logic.db_init()
            from .plugin import plugin_info
            Util.save_from_dict_to_json(plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))

            tmp = os.path.join(path_data, package_name)
            if not os.path.exists(tmp):
                os.makedirs(tmp)
            if not os.path.exists(ModelSetting.get('path_accounts')):
                os.makedirs(ModelSetting.get('path_accounts'))
            try:
                from google_auth_oauthlib.flow import InstalledAppFlow
            except:
                os.system("{} install google_auth_oauthlib".format(app.config['config']['pip']))
                from google_auth_oauthlib.flow import InstalledAppFlow

            tmp = os.path.join(os.path.dirname(__file__), 'bin')
            if os.path.exists(tmp):
                os.system('chmod 777 -R %s' % tmp)
            if ModelSetting.query.filter_by(key='gsheet_auto_start').first().value == 'True':
                Logic.scheduler_start()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def plugin_unload():
        try:
            logger.debug('%s plugin_unload', package_name)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def scheduler_start():
        try:
            job = Job(package_name, "rclone_expand_gsheet", ModelSetting.get('gsheet_interval'), Logic.scheduler_function, u"RCloneExpend for GSheet", False)
            scheduler.add_job_instance(job)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    
    @staticmethod
    def scheduler_stop():
        try:
            scheduler.remove_job("rclone_expand_gsheet")
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def scheduler_function():
        try:
            if app.config['config']['use_celery']:
                result = LogicGSheet.scheduler_function.apply_async()
                result.get()
            else:
                LogicGSheet.scheduler_function()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def migration():
        LogicGSheet.ws_ir_init()
        LogicGSheet.google_api_auth()
        # TEMP CODE
        try:
            # for temporary: ListModelItem Table alter
            import sqlite3
            db_path = os.path.join(path_data, 'db', '%s.db' % package_name)
            table_name = '%s_listitem' % package_name

            if platform.system() is 'Linux':
                # connect to read only for Linux
                fd = os.open(db_path, os.O_RDWR)
                conn = sqlite3.connect('/dev/fd/%d' % fd)
                os.close(fd)
            else:
                conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            q = 'PRAGMA table_info("{table_name}")'.format(table_name=table_name)
            alter_byte_size = True
            alter_updated_time = True
            alter_excluded = True
            alter_mimetype = True
            for row in cur.execute(q).fetchall():
                if row[1] == 'byte_size': alter_byte_size = False
                if row[1] == 'updated_time': alter_updated_time = False
                if row[1] == 'excluded': alter_excluded = False
                if row[1] == 'mimetype': alter_mimetype = False

            if alter_byte_size is False and alter_updated_time is False and alter_excluded is False and alter_mimetype is False:
                conn.close()
                return

            if alter_byte_size:
                query = 'ALTER TABLE {table_name} ADD COLUMN byte_size INTEGER default 0'.format(table_name=table_name)
                cur.execute(query)
                logger.info('LiteModelItem Alterred(column: byte_size)')
            if alter_updated_time:
                query = 'ALTER TABLE {table_name} ADD COLUMN updated_time DATETIME default NULL'.format(table_name=table_name)
                cur.execute(query)
                logger.info('LiteModelItem Alterred(column: updated_time)')
            if alter_excluded:
                query = 'ALTER TABLE {table_name} ADD COLUMN excluded INTEGER default 0'.format(table_name=table_name)
                cur.execute(query)
                logger.info('LiteModelItem Alterred(column: excluded)')
            if alter_mimetype:
                query = 'ALTER TABLE {table_name} ADD COLUMN mimetype INTEGER default 0'.format(table_name=table_name)
                cur.execute(query)
                logger.info('LiteModelItem Alterred(column: mimetype)')
            conn.commit()
            conn.close()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    ##################################################################################

    

    
