from datetime import time
import asyncio
import os
import requests
import warnings
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    TypeHandler,
    filters,
)
from telegram.warnings import PTBUserWarning

# Suppress per_message ConversationHandler warnings (expected behavior for our bot)
warnings.filterwarnings('ignore', message='.*per_message.*', category=PTBUserWarning)

from .handlers.admin_settings import (
    admin_wallet_adjust_menu,
    admin_toggle_join_logs,
    admin_set_join_logs_chat_start,
    admin_toggle_purchase_logs,
    admin_set_purchase_logs_chat_start,
    admin_settings_save_log_chat,
)
from .handlers.admin_users import (
    admin_users_menu,
    admin_users_page,
    admin_users_search_start,
    admin_users_search_apply,
    admin_users_toggle_ban,
    admin_users_export_csv,
    admin_users_view_by_id_start,
    admin_users_view_by_id_show,
    admin_users_view_by_id_callback,
    admin_users_toggle_ban_inline,
    admin_users_show_services,
    admin_users_show_tickets,
    admin_users_show_wallet,
    admin_users_show_refs,
)
from .handlers.admin_service_actions import (
    admin_service_renew_confirm,
    admin_service_renew_execute,
    admin_service_delete_confirm,
    admin_service_delete_execute,
)
from .handlers.admin_cron import (
    admin_cron_menu,
    admin_cron_toggle_reminders,
    admin_cron_set_hour_start,
    admin_cron_set_hour_save,
)

from .config import BOT_TOKEN, DAILY_JOB_HOUR
from .db import query_db
from .db import db_setup
from .jobs import check_expirations
from .jobs.notifications import check_low_traffic_and_expiry
from .handlers.common import force_join_checker, dynamic_button_handler, start_command
from .handlers.cancel import cancel_flow, cancel_admin_flow
from .handlers.admin import (
    send_admin_panel,
    admin_command,
    master_message_handler,
    admin_ask_panel_for_approval,
    admin_approve_on_panel,
    admin_review_order_reject,
    admin_manual_send_start,
    admin_approve_renewal,
    admin_settings_manage,
    admin_toggle_bot_active,
    admin_toggle_trial_status,
    admin_settings_ask,
    admin_settings_save_trial,
    admin_settings_save_payment_text,
    backup_start,
    admin_generate_backup,
    backup_restore_start,
    backup_restore_receive_file,
    cancel_admin_conversation,
    exit_admin_panel,
    # admin_run_reminder_check,
    process_send_by_id_get_id,
    process_send_by_id_get_message,
    admin_send_by_id_start,
    admin_admins_menu,
    admin_add_command,
    admin_del_command, admin_setms_command,
    admin_set_payment_text_start, admin_set_usd_rate_start_global,
    admin_wallet_tx_menu, admin_wallet_tx_view, admin_wallet_tx_approve, admin_wallet_tx_reject,
    admin_wallet_adjust_start, admin_wallet_adjust_text_router,
    admin_set_usd_rate_start, admin_set_usd_rate_save,
    # admin_toggle_signup_bonus, admin_set_signup_bonus_amount_start, admin_set_signup_bonus_amount_save,
    admin_set_trial_panel_start, admin_set_trial_panel_choose,
    admin_set_ref_percent_start, admin_set_ref_percent_save, admin_set_config_footer_start, admin_set_config_footer_save,
    admin_set_gateway_api_start, admin_set_gateway_api_save,
    admin_set_trial_inbound_start, admin_set_trial_inbound_choose,
    admin_toggle_pay_card, admin_toggle_pay_crypto, admin_toggle_pay_gateway, admin_toggle_gateway_type,
    admin_xui_choose_inbound,
    admin_reseller_menu, admin_toggle_reseller, admin_reseller_requests, admin_reseller_set_value_start, admin_reseller_set_value_save, admin_reseller_approve, admin_reseller_reject, admin_reseller_delete_start, admin_reseller_delete_receive,
    admin_toggle_signup_bonus, admin_set_signup_bonus_amount_start, admin_set_signup_bonus_amount_save,
    admin_orders_menu, admin_orders_manage, admin_orders_pending, admin_user_management, admin_payments_menu,
    admin_quick_backup,
)
from .handlers.user import (
    get_free_config_handler, my_services_handler, show_specific_service_details, wallet_menu,
    wallet_topup_gateway_start, wallet_topup_gateway_receive_amount, wallet_topup_card_start,
    wallet_topup_card_receive_amount, wallet_verify_gateway,
    wallet_topup_crypto_start, wallet_topup_crypto_receive_amount, wallet_topup_amount_router,
    wallet_topup_custom_amount_start, wallet_topup_custom_amount_receive,
    support_menu, ticket_create_start, ticket_receive_message, tutorials_menu, tutorial_show,
    referral_menu, wallet_select_amount, wallet_upload_start_card, wallet_upload_start_crypto,
    composite_upload_router, refresh_service_link, revoke_key, view_service_qr, delete_service_start, delete_service_confirm,
    check_service_status, card_to_card_info,
    reseller_menu, reseller_pay_start,
    reseller_pay_card, reseller_pay_crypto, reseller_pay_gateway, reseller_verify_gateway,
    reseller_upload_start_card, reseller_upload_start_crypto, reseller_upload_router
)
from .handlers.purchase import (
    start_purchase_flow as start_purchase_flow,
    show_plan_confirmation as show_plan_confirmation,
    apply_discount_start as apply_discount_start,
    receive_and_validate_discount_code as receive_and_validate_discount_code,
    receive_payment_screenshot as receive_payment_screenshot,
    show_payment_method_selection as show_payment_method_selection,
    pay_method_wallet as pay_method_wallet,
    show_payment_info_card as show_payment_info_card,
    show_payment_info_crypto as show_payment_info_crypto,
    show_payment_info_gateway as show_payment_info_gateway,
    set_cust_username_start as set_cust_username_start,
    save_custom_username as save_custom_username,
)
from .handlers.renewal import (
    start_renewal_flow,
    show_renewal_plan_confirmation,
    renew_apply_discount_start,
    receive_renewal_payment,
)
from .states import *
from .utils import register_new_user
from .handlers.admin_cards import admin_cards_menu as admin_cards_menu, admin_card_add_start, admin_card_delete, admin_card_edit_start, admin_card_edit_ask_value, admin_card_add_receive_number, admin_card_add_save
from .handlers.admin_wallets import admin_wallets_menu as admin_wallets_menu, admin_wallet_add_start, admin_wallet_add_receive_asset, admin_wallet_add_receive_chain, admin_wallet_add_receive_address, admin_wallet_add_save, admin_wallet_delete, admin_wallet_edit_start, admin_wallet_edit_ask_value
from .handlers.admin_plans import (
    admin_plan_manage as admin_plan_manage,
    admin_plan_delete as admin_plan_delete,
    admin_plan_add_start as admin_plan_add_start,
    admin_plan_receive_name as admin_plan_receive_name,
    admin_plan_receive_desc as admin_plan_receive_desc,
    admin_plan_receive_price as admin_plan_receive_price,
    admin_plan_receive_days as admin_plan_receive_days,
    admin_plan_save as admin_plan_save,
    admin_plan_edit_start as admin_plan_edit_start,
    admin_plan_edit_ask_value as admin_plan_edit_ask_value,
    admin_plan_edit_save as admin_plan_edit_save,
    admin_plan_bind_start as admin_plan_bind_start,
    admin_plan_bind_panel_choose as admin_plan_bind_panel_choose,
    admin_plan_bind_inbound_choose as admin_plan_bind_inbound_choose,
)
from .handlers.admin_discounts import (
    admin_discount_menu as admin_discount_menu,
    admin_discount_add_start,
    admin_discount_delete,
    admin_discount_receive_code,
    admin_discount_receive_percent,
    admin_discount_receive_limit,
    admin_discount_save,
)
from .handlers.admin_settings import (
    admin_settings_manage as admin_settings_manage,
    admin_toggle_trial_status as admin_toggle_trial_status,
    admin_toggle_usd_mode as admin_toggle_usd_mode,
    admin_settings_ask as admin_settings_ask,
    admin_settings_save_trial as admin_settings_save_trial,
    admin_settings_save_payment_text as admin_settings_save_payment_text,
    admin_toggle_user_quota as admin_toggle_user_quota,
    admin_toggle_talert as admin_toggle_talert,
    admin_set_talert_gb_start as admin_set_talert_gb_start,
    admin_set_time_alert_days_start as admin_set_time_alert_days_start,
    admin_toggle_time_alert as admin_toggle_time_alert,
    admin_toggle_auto_backup as admin_toggle_auto_backup,
    admin_set_auto_backup_hours_start as admin_set_auto_backup_hours_start,
    admin_set_talert_value_save as admin_set_talert_value_save,
    admin_run_alerts_now as admin_run_alerts_now,
    admin_settings_send_test_join_log as admin_settings_send_test_join_log,
    admin_settings_send_test_purchase_log as admin_settings_send_test_purchase_log,
)
from .handlers.admin_panels import (
    admin_panels_menu as admin_panels_menu,
    admin_panel_add_start,
    admin_panel_delete,
    admin_panel_inbounds_menu,
    admin_panel_inbound_delete,
    admin_panel_inbound_add_start,
    admin_panel_inbound_receive_protocol,
    admin_panel_inbound_receive_tag,
    admin_panel_receive_name,
    admin_panel_receive_type,
    admin_panel_receive_url,
    admin_panel_receive_sub_base,
    admin_panel_receive_token,
    admin_panel_receive_user,
    admin_panel_receive_pass,
    admin_panel_receive_default_inbound,
    admin_panel_toggle_enabled,
    admin_panel_health_check,
)
from .handlers.admin_messages import (
    admin_messages_menu as admin_messages_menu,
    admin_messages_select as admin_messages_select,
    admin_messages_edit_text_start as admin_messages_edit_text_start,
    admin_messages_edit_text_save as admin_messages_edit_text_save,
    admin_buttons_menu as admin_buttons_menu,
    admin_button_edit_start as admin_button_edit_start,
    admin_button_edit_ask_value as admin_button_edit_ask_value,
    admin_button_edit_set_is_url as admin_button_edit_set_is_url,
    admin_button_add_start as admin_button_add_start,
    admin_button_add_receive_text as admin_button_add_receive_text,
    admin_button_add_receive_target as admin_button_add_receive_target,
    admin_button_add_receive_is_url as admin_button_add_receive_is_url,
    admin_button_add_receive_row as admin_button_add_receive_row,
    admin_button_add_save as admin_button_add_save,
    admin_button_delete as admin_button_delete,
    msg_add_start as msg_add_start,
    msg_add_receive_name as msg_add_receive_name,
    msg_add_receive_content as msg_add_receive_content,
    admin_messages_delete as admin_messages_delete,
)
from .handlers.admin import admin_panel_inbounds_refresh
from .handlers.admin import admin_run_reminder_check as premium_admin_run_reminder_check
from .handlers.admin_tickets import (
    admin_tickets_menu as admin_tickets_menu,
    admin_ticket_view,
    admin_ticket_delete,
    admin_ticket_reply_start,
    admin_ticket_receive_reply,
)
from .handlers.admin_tutorials import (
    admin_tutorials_menu as admin_tutorials_menu,
    admin_tutorial_add_start,
    admin_tutorial_receive_title,
    admin_tutorial_receive_media,
    admin_tutorial_delete,
    admin_tutorial_view,
    admin_tutorial_finish,
    admin_tutorial_media_page,
    admin_tutorial_edit_title_start,
    admin_tutorial_media_delete,
    admin_tutorial_media_move,
)
from .handlers.admin_stats_broadcast import (
    admin_stats_menu as admin_stats_menu,
    admin_stats_refresh as admin_stats_refresh,
    admin_broadcast_set_mode as admin_broadcast_set_mode,
)
from .handlers.admin_stats_broadcast import (
    admin_broadcast_menu as admin_broadcast_menu,
    admin_broadcast_ask_message as admin_broadcast_ask_message,
    admin_broadcast_execute as admin_broadcast_execute,
)
from .handlers.admin_system import admin_system_health, admin_clear_notifications

async def debug_text_logger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        uid = update.effective_user.id if update.effective_user else None
        txt = (update.message.text or '')[:100] if update.message else ''
        flags = {
            'awaiting': context.user_data.get('awaiting'),
            'awaiting_admin': context.user_data.get('awaiting_admin'),
            'awaiting_ticket': context.user_data.get('awaiting_ticket'),
            'next_action': context.user_data.get('next_action'),
        }
        from .config import logger
        logger.debug(f"debug_text_logger: uid={uid} text='{txt}' flags={flags}")
    except Exception:
        pass


def build_application() -> Application:
    db_setup()
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)
        .pool_timeout(30.0)  # Timeout for connection pool
        .connection_pool_size(8)  # Limit concurrent connections
        .connect_timeout(20.0)  # Connection timeout
        .read_timeout(20.0)  # Read timeout
        .write_timeout(20.0)  # Write timeout
        .get_updates_pool_timeout(1.0)  # Reduced timeout for polling
        .build()
    )

    if application.job_queue:
        try:
            st = query_db("SELECT value FROM settings WHERE key='daily_job_hour'", one=True)
            hour = int((st or {}).get('value') or DAILY_JOB_HOUR)
        except Exception:
            hour = DAILY_JOB_HOUR
        application.job_queue.run_daily(check_expirations, time=time(hour=hour, minute=0, second=0), name="daily_expiration_check")
        # Traffic and expiry notifications - run every 24 hours (reduced from 12h to minimize panel logins)
        application.job_queue.run_repeating(check_low_traffic_and_expiry, interval=24*3600, first=600, name="notification_check")
        # Auto-backup scheduling
        from .config import logger
        try:
            ab_enabled = (query_db("SELECT value FROM settings WHERE key='auto_backup_enabled'", one=True) or {}).get('value') == '1'
            ab_hours = int((query_db("SELECT value FROM settings WHERE key='auto_backup_hours'", one=True) or {}).get('value') or '3')
        except Exception as e:
            logger.warning(f"Auto-backup config error: {e}, using defaults")
            ab_enabled = False; ab_hours = 3
        if ab_enabled and ab_hours > 0:
            interval_seconds = ab_hours * 3600
            logger.info(f"Auto-backup enabled: every {ab_hours} hours ({interval_seconds} seconds)")
            from .jobs import backup_and_send_to_admins
            application.job_queue.run_repeating(backup_and_send_to_admins, interval=interval_seconds, first=60, name="auto_backup_send")
        else:
            logger.info(f"Auto-backup disabled or invalid (enabled={ab_enabled}, hours={ab_hours})")

    application.add_handler(TypeHandler(Update, force_join_checker), group=-1)
    # Early debug logger for text messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, debug_text_logger), group=-1)
    # Route master text handler AFTER conversations so stateful flows (e.g., add panel URL/user/pass) capture inputs first
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, master_message_handler), group=2)

    admin_conv = ConversationHandler(
        entry_points=[CommandHandler('admin', admin_command)],
        states={
            ADMIN_MAIN_MENU: [
                CallbackQueryHandler(admin_plan_manage, pattern='^admin_plan_manage$'),
                CallbackQueryHandler(admin_settings_manage, pattern='^admin_settings_manage$'),
                CallbackQueryHandler(admin_toggle_bot_active, pattern='^admin_toggle_bot_active$'),
                CallbackQueryHandler(admin_users_menu, pattern='^admin_users_menu$'),
                CallbackQueryHandler(admin_user_management, pattern='^admin_user_management$'),
                CallbackQueryHandler(admin_cron_menu, pattern='^admin_cron_menu$'),
                CallbackQueryHandler(admin_messages_menu, pattern='^admin_messages_menu$'),
                CallbackQueryHandler(admin_broadcast_menu, pattern='^admin_broadcast_menu$'),
                CallbackQueryHandler(admin_send_by_id_start, pattern='^admin_send_by_id_start$'),

                CallbackQueryHandler(admin_admins_menu, pattern='^admin_admins_menu$'),
                                CallbackQueryHandler(admin_discount_menu, pattern='^admin_discount_menu$'),
                CallbackQueryHandler(admin_panels_menu, pattern='^admin_panels_menu$'),
                CallbackQueryHandler(backup_start, pattern='^backup_start$'),
                CallbackQueryHandler(backup_restore_start, pattern='^backup_restore_start$'),
                CallbackQueryHandler(premium_admin_run_reminder_check, pattern=r'^admin_test_reminder$'),
                CallbackQueryHandler(admin_tickets_menu, pattern='^admin_tickets_menu$'),
                CallbackQueryHandler(admin_tutorials_menu, pattern='^admin_tutorials_menu$'),
                CallbackQueryHandler(admin_system_health, pattern='^admin_system_health$'),
                CallbackQueryHandler(admin_clear_notifications, pattern='^admin_clear_notifications$'),
                CallbackQueryHandler(admin_wallet_tx_menu, pattern='^admin_wallet_tx_menu$'),
                CallbackQueryHandler(admin_orders_menu, pattern='^admin_orders_menu$'),
            ],
            ADMIN_USERS_MENU: [
                CallbackQueryHandler(admin_users_page, pattern=r'^admin_users_page_\d+$'),
                CallbackQueryHandler(admin_users_toggle_ban, pattern=r'^admin_user_toggle_\d+$'),
                CallbackQueryHandler(admin_users_export_csv, pattern=r'^admin_users_export$'),
                CallbackQueryHandler(admin_users_search_start, pattern=r'^admin_users_search$'),
                CallbackQueryHandler(admin_users_view_by_id_start, pattern=r'^admin_user_view_prompt$'),
                CallbackQueryHandler(admin_users_view_by_id_callback, pattern=r'^admin_user_view_\d+$'),
                CallbackQueryHandler(admin_users_toggle_ban_inline, pattern=r'^admin_user_ban_(yes|no)_\d+$'),
                CallbackQueryHandler(admin_users_toggle_ban_inline, pattern=r'^admin_user_ban_\d+$'),
                CallbackQueryHandler(admin_users_show_services, pattern=r'^admin_user_services_\d+(_page_\d+)?$'),
                CallbackQueryHandler(admin_users_show_tickets, pattern=r'^admin_user_tickets_\d+(_page_\d+)?$'),
                CallbackQueryHandler(admin_users_show_wallet, pattern=r'^admin_user_wallet_\d+(_page_\d+)?$'),
                CallbackQueryHandler(admin_users_show_refs, pattern=r'^admin_user_refs_\d+(_page_\d+)?$'),
                # Admin service actions
                CallbackQueryHandler(admin_service_renew_confirm, pattern=r'^admin_service_renew_\d+_\d+$'),
                CallbackQueryHandler(admin_service_renew_execute, pattern=r'^admin_service_renew_yes_\d+_\d+$'),
                CallbackQueryHandler(admin_service_delete_confirm, pattern=r'^admin_service_delete_\d+_\d+$'),
                CallbackQueryHandler(admin_service_delete_execute, pattern=r'^admin_service_delete_yes_\d+_\d+$'),
                CallbackQueryHandler(admin_command, pattern='^admin_main$'),
            ],
            ADMIN_USERS_AWAIT_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_users_search_apply)],
            ADMIN_CRON_MENU: [
                CallbackQueryHandler(admin_cron_toggle_reminders, pattern=r'^cron_toggle_reminders_(0|1)$'),
                CallbackQueryHandler(admin_cron_set_hour_start, pattern=r'^cron_set_hour_start$'),
                CallbackQueryHandler(admin_command, pattern='^admin_main$'),
            ],
            ADMIN_CRON_AWAIT_HOUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_cron_set_hour_save)],
            BACKUP_CHOOSE_PANEL: [
                CallbackQueryHandler(admin_generate_backup, pattern=r'^backup_panel_(all|\d+)$'),
            ],
            BACKUP_RESTORE_AWAIT_FILE: [
                MessageHandler(filters.Document.ALL, backup_restore_receive_file),
            ],
            ADMIN_MESSAGES_MENU: [
                CallbackQueryHandler(admin_messages_select, pattern=r'^msg_select_.+'),
                CallbackQueryHandler(msg_add_start, pattern=r'^msg_add_start$'),
                CallbackQueryHandler(admin_messages_menu, pattern=r'^admin_messages_menu$'),
                CallbackQueryHandler(admin_messages_menu, pattern=r'^admin_messages_menu_page_\d+$'),
                CallbackQueryHandler(admin_command, pattern='^admin_main$'),
            ],
            ADMIN_MESSAGES_SELECT: [
                CallbackQueryHandler(admin_messages_edit_text_start, pattern=r'^msg_action_edit_text$'),
                CallbackQueryHandler(admin_buttons_menu, pattern=r'^msg_action_edit_buttons$'),
                CallbackQueryHandler(admin_messages_delete, pattern=r'^msg_delete_current$'),
                CallbackQueryHandler(admin_button_delete, pattern=r'^btn_delete_\d+$'),
                CallbackQueryHandler(admin_button_edit_start, pattern=r'^btn_edit_\d+$'),
                CallbackQueryHandler(admin_button_add_start, pattern=r'^btn_add_new$'),
                CallbackQueryHandler(admin_button_edit_ask_value, pattern=r'^btn_edit_field_(text|target|isurl|row|col)$'),
                CallbackQueryHandler(admin_button_edit_set_is_url, pattern=r'^btn_set_isurl_\d+_(0|1)$'),
                CallbackQueryHandler(admin_messages_select, pattern=r'^msg_select_.+'),
                CallbackQueryHandler(admin_messages_menu, pattern=r'^admin_messages_menu$'),
                CallbackQueryHandler(admin_messages_menu, pattern=r'^admin_messages_menu_page_\d+$'),
                CallbackQueryHandler(admin_command, pattern='^admin_main$'),
            ],
            ADMIN_MESSAGES_EDIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_messages_edit_text_save)],
            ADMIN_BUTTON_ADD_AWAIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_button_add_receive_text)],
            ADMIN_BUTTON_ADD_AWAIT_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_button_add_receive_target)],
            ADMIN_BUTTON_ADD_AWAIT_URL: [CallbackQueryHandler(admin_button_add_receive_is_url, pattern=r'^btn_isurl_(0|1)$')],
            ADMIN_BUTTON_ADD_AWAIT_ROW: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_button_add_receive_row)],
            ADMIN_BUTTON_ADD_AWAIT_COL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_button_add_save)],
            ADMIN_MESSAGES_ADD_AWAIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, msg_add_receive_name)],
            ADMIN_MESSAGES_ADD_AWAIT_CONTENT: [MessageHandler(filters.ALL & ~filters.COMMAND, msg_add_receive_content)],
            # Discount Codes Management
            DISCOUNT_MENU: [
                CallbackQueryHandler(admin_discount_add_start, pattern='^add_discount_code$'),
                CallbackQueryHandler(admin_discount_delete, pattern=r'^delete_discount_\d+$'),
                CallbackQueryHandler(admin_discount_menu, pattern='^admin_discount_menu$'),
                CallbackQueryHandler(admin_command, pattern='^admin_main$'),
            ],
            DISCOUNT_AWAIT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_discount_receive_code)],
            DISCOUNT_AWAIT_PERCENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_discount_receive_percent)],
            DISCOUNT_AWAIT_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_discount_receive_limit)],
            DISCOUNT_AWAIT_EXPIRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_discount_save)],
            # Panels Management
            ADMIN_PANELS_MENU: [
                CallbackQueryHandler(admin_panel_inbounds_menu, pattern=r'^panel_inbounds_\d+$'),
                CallbackQueryHandler(admin_panel_delete, pattern=r'^panel_delete_\d+$'),
                CallbackQueryHandler(admin_panel_toggle_enabled, pattern=r'^panel_toggle_\d+$'),
                CallbackQueryHandler(admin_panel_health_check, pattern=r'^panel_health_\d+$'),
                CallbackQueryHandler(admin_panel_add_start, pattern='^panel_add_start$'),
                CallbackQueryHandler(admin_panels_menu, pattern='^admin_panels_menu$'),
                CallbackQueryHandler(admin_command, pattern='^admin_main$'),
            ],
            ADMIN_PANEL_AWAIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_panel_receive_name)],
            ADMIN_PANEL_AWAIT_TYPE: [CallbackQueryHandler(admin_panel_receive_type, pattern=r'^panel_type_')],
            ADMIN_PANEL_AWAIT_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_panel_receive_url)],
            ADMIN_PANEL_AWAIT_SUB_BASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_panel_receive_sub_base)],
            ADMIN_PANEL_AWAIT_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_panel_receive_token)],
            ADMIN_PANEL_AWAIT_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_panel_receive_user)],
            ADMIN_PANEL_AWAIT_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_panel_receive_pass)],
            ADMIN_PANEL_AWAIT_DEFAULT_INBOUND: [CallbackQueryHandler(admin_panel_receive_default_inbound, pattern=r'^panel_inbound_')],
            # Panel Inbounds Editor
            ADMIN_PANEL_INBOUNDS_MENU: [
                CallbackQueryHandler(admin_panel_inbound_delete, pattern=r'^inbound_delete_\d+$'),
                CallbackQueryHandler(admin_panel_inbound_add_start, pattern=r'^inbound_add_start$'),
                CallbackQueryHandler(admin_panel_inbounds_refresh, pattern=r'^inbound_refresh$'),
                CallbackQueryHandler(admin_panels_menu, pattern=r'^admin_panels_menu$'),
                CallbackQueryHandler(admin_panel_inbounds_menu, pattern=r'^panel_inbounds_\d+$'),
                CallbackQueryHandler(admin_command, pattern='^admin_main$'),
            ],
            ADMIN_PANEL_INBOUNDS_AWAIT_PROTOCOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_panel_inbound_receive_protocol)],
            ADMIN_PANEL_INBOUNDS_AWAIT_TAG: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_panel_inbound_receive_tag)],
            ADMIN_PLAN_MENU: [
                CallbackQueryHandler(admin_plan_delete, pattern=r'^plan_delete_\d+$'),
                CallbackQueryHandler(admin_plan_edit_start, pattern=r'^plan_edit_\d+$'),
                CallbackQueryHandler(admin_plan_add_start, pattern='^plan_add$'),
                CallbackQueryHandler(admin_command, pattern='^admin_main$'),
            ],
            ADMIN_PLAN_AWAIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_plan_receive_name)],
            ADMIN_PLAN_AWAIT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_plan_receive_desc)],
            ADMIN_PLAN_AWAIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_plan_receive_price)],
            ADMIN_PLAN_AWAIT_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_plan_receive_days)],
            ADMIN_PLAN_AWAIT_GIGABYTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_plan_save)],
            ADMIN_PLAN_EDIT_MENU: [
                CallbackQueryHandler(admin_plan_edit_ask_value, pattern=r'^edit_plan_'),
                CallbackQueryHandler(admin_plan_manage, pattern='^admin_plan_manage$'),
                CallbackQueryHandler(admin_plan_bind_panel_choose, pattern=r'^plan_bind_panel_\d+$'),
                CallbackQueryHandler(admin_plan_bind_inbound_choose, pattern=r'^plan_bind_inb_\d+_\d+$'),
                CallbackQueryHandler(admin_command, pattern='^admin_main$'),
            ],
            ADMIN_PLAN_EDIT_AWAIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_plan_edit_save)],
            ADMIN_PLAN_BIND_PANEL: [
                CallbackQueryHandler(admin_plan_bind_panel_choose, pattern=r'^plan_bind_panel_\d+$'),
                CallbackQueryHandler(admin_plan_edit_start, pattern=r'^plan_edit_\d+$'),
                CallbackQueryHandler(admin_plan_manage, pattern='^admin_plan_manage$'),
            ],
            ADMIN_PLAN_BIND_INBOUND: [
                CallbackQueryHandler(admin_plan_bind_inbound_choose, pattern=r'^plan_bind_inb_\d+_\d+$'),
                CallbackQueryHandler(admin_plan_edit_start, pattern=r'^plan_edit_\d+$'),
                CallbackQueryHandler(admin_plan_manage, pattern='^admin_plan_manage$'),
            ],
            ADMIN_STATS_MENU: [
                CallbackQueryHandler(admin_stats_refresh, pattern='^stats_refresh$'),
                CallbackQueryHandler(admin_command, pattern='^admin_main$'),
            ],
            BROADCAST_SELECT_AUDIENCE: [
                CallbackQueryHandler(admin_broadcast_ask_message, pattern=r'^broadcast_(all|buyers)$'),
            ],
            BROADCAST_SELECT_MODE: [
                CallbackQueryHandler(admin_broadcast_set_mode, pattern=r'^broadcast_mode_(copy|forward)$'),
            ],
            BROADCAST_AWAIT_MESSAGE: [
                MessageHandler(filters.ALL & ~filters.COMMAND, admin_broadcast_execute),
            ],
            SETTINGS_MENU: [
                CallbackQueryHandler(admin_settings_ask, pattern=r'^set_(trial_days|payment_text)$'),
                CallbackQueryHandler(admin_toggle_trial_status, pattern=r'^set_trial_status_(0|1)$'),
                CallbackQueryHandler(admin_cards_menu, pattern='^admin_cards_menu$'),
                CallbackQueryHandler(admin_wallets_menu, pattern='^admin_wallets_menu$'),
                CallbackQueryHandler(admin_wallet_tx_menu, pattern='^admin_wallet_tx_menu$'),
                CallbackQueryHandler(admin_set_usd_rate_start, pattern='^set_usd_rate_start$'),
                CallbackQueryHandler(admin_set_trial_panel_start, pattern='^set_trial_panel_start$'),
                CallbackQueryHandler(admin_set_trial_panel_choose, pattern=r'^set_trial_panel_\d+$'),
                CallbackQueryHandler(admin_set_trial_inbound_start, pattern='^set_trial_inbound_start$'),
                CallbackQueryHandler(admin_set_ref_percent_start, pattern='^set_ref_percent_start$'),
                CallbackQueryHandler(admin_set_config_footer_start, pattern='^set_config_footer_start$'),
                CallbackQueryHandler(admin_toggle_usd_mode, pattern=r'^toggle_usd_mode_(manual|api)$'),
                CallbackQueryHandler(admin_toggle_pay_card, pattern=r'^toggle_pay_card_(0|1)$'),
                CallbackQueryHandler(admin_toggle_pay_crypto, pattern=r'^toggle_pay_crypto_(0|1)$'),
                CallbackQueryHandler(admin_toggle_pay_gateway, pattern=r'^toggle_pay_gateway_(0|1)$'),
                CallbackQueryHandler(admin_toggle_gateway_type, pattern=r'^toggle_gateway_type_(zarinpal|aghapay)$'),
                CallbackQueryHandler(admin_set_trial_inbound_choose, pattern=r'^set_trial_inbound_\d+$'),
                CallbackQueryHandler(admin_toggle_signup_bonus, pattern=r'^toggle_signup_bonus_(0|1)$'),
                CallbackQueryHandler(admin_set_signup_bonus_amount_start, pattern='^set_signup_bonus_amount$'),
                CallbackQueryHandler(admin_set_gateway_api_start, pattern='^set_gateway_api_start$'),
                CallbackQueryHandler(admin_toggle_user_quota, pattern=r'^toggle_user_quota_(0|1)$'),
                CallbackQueryHandler(admin_toggle_talert, pattern=r'^toggle_talert_(0|1)$'),
                CallbackQueryHandler(admin_set_talert_gb_start, pattern='^set_talert_gb_start$'),
                CallbackQueryHandler(admin_toggle_time_alert, pattern=r'^toggle_time_alert_(0|1)$'),
                CallbackQueryHandler(admin_set_time_alert_days_start, pattern='^set_time_alert_days_start$'),
                # Auto-backup controls
                CallbackQueryHandler(admin_toggle_auto_backup, pattern=r'^toggle_auto_backup_(0|1)$'),
                CallbackQueryHandler(admin_set_auto_backup_hours_start, pattern='^set_auto_backup_hours_start$'),
                CallbackQueryHandler(admin_run_alerts_now, pattern='^run_alerts_now$'),
                # Test log buttons
                CallbackQueryHandler(admin_settings_send_test_join_log, pattern='^test_join_log$'),
                CallbackQueryHandler(admin_settings_send_test_purchase_log, pattern='^test_purchase_log$'),
                CallbackQueryHandler(admin_settings_manage, pattern='^admin_settings_manage$'),
                CallbackQueryHandler(admin_command, pattern='^admin_main$'),
                # Reseller settings
                CallbackQueryHandler(admin_reseller_menu, pattern='^admin_reseller_menu$'),
                CallbackQueryHandler(admin_toggle_reseller, pattern=r'^toggle_reseller_(0|1)$'),
                CallbackQueryHandler(admin_reseller_requests, pattern='^admin_reseller_requests$'),
                CallbackQueryHandler(admin_reseller_set_value_start, pattern=r'^(set_reseller_fee|set_reseller_percent|set_reseller_days|set_reseller_cap)$'),
                CallbackQueryHandler(admin_wallet_adjust_menu, pattern='^admin_wallet_adjust_menu$'),
            ],
            ADMIN_WALLET_MENU: [
                CallbackQueryHandler(admin_wallet_tx_menu, pattern='^admin_wallet_tx_menu$'),
                CallbackQueryHandler(admin_wallet_tx_view, pattern=r'^wallet_tx_view_\d+$'),
                CallbackQueryHandler(admin_wallet_tx_approve, pattern=r'^wallet_tx_approve_\d+$'),
                CallbackQueryHandler(admin_wallet_tx_reject, pattern=r'^wallet_tx_reject_\d+$'),
                CallbackQueryHandler(admin_wallet_adjust_start, pattern=r'^wallet_adjust_start_(credit|debit)$'),
            ],
                         ADMIN_CARDS_MENU: [
                 CallbackQueryHandler(admin_card_add_start, pattern='^card_add_start$'),
                 CallbackQueryHandler(admin_card_delete, pattern=r'^card_delete_'),
                 CallbackQueryHandler(admin_card_edit_start, pattern=r'^card_edit_\d+$'),
                 CallbackQueryHandler(admin_card_edit_ask_value, pattern=r'^card_edit_field_(number|holder)$'),
                 CallbackQueryHandler(admin_settings_manage, pattern='^admin_settings_manage$'),
             ],
            ADMIN_CARDS_AWAIT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_card_add_receive_number)],
            ADMIN_CARDS_AWAIT_HOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_card_add_save)],
                         ADMIN_WALLETS_MENU: [
                 CallbackQueryHandler(admin_wallet_add_start, pattern='^wallet_add_start$'),
                 CallbackQueryHandler(admin_wallet_delete, pattern=r'^wallet_delete_'),
                 CallbackQueryHandler(admin_wallet_edit_start, pattern=r'^wallet_edit_\d+$'),
                 CallbackQueryHandler(admin_wallet_edit_ask_value, pattern=r'^wallet_edit_field_(asset|chain|address|memo)$'),
                 CallbackQueryHandler(admin_settings_manage, pattern='^admin_settings_manage$'),
             ],
            ADMIN_WALLETS_AWAIT_ASSET: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_wallet_add_receive_asset)],
            ADMIN_WALLETS_AWAIT_CHAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_wallet_add_receive_chain)],
            ADMIN_WALLETS_AWAIT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_wallet_add_receive_address)],
            ADMIN_WALLETS_AWAIT_MEMO: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_wallet_add_save)],
            SETTINGS_AWAIT_TRIAL_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_settings_save_trial)],
            SETTINGS_AWAIT_PAYMENT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_settings_save_payment_text)],
            SETTINGS_AWAIT_USD_RATE: [
                # First, try saving log chat IDs when awaiting_admin flag is set for logs
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_settings_save_log_chat),
                # Otherwise, treat as USD rate save
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_usd_rate_save),
            ],
            SETTINGS_AWAIT_SIGNUP_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_signup_bonus_amount_save)],
            SETTINGS_AWAIT_GATEWAY_API: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_gateway_api_save)],
            SETTINGS_AWAIT_TRAFFIC_ALERT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_talert_value_save)],
            ADMIN_RESELLER_AWAIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_reseller_set_value_save)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_admin_conversation),
            CallbackQueryHandler(exit_admin_panel, pattern='^admin_exit$'),
            CallbackQueryHandler(admin_command, pattern='^admin_main$'),
        ],
        allow_reentry=True,
        per_message=False,
    )

    purchase_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_purchase_flow, pattern='^buy_config_main$')],
        states={
            SELECT_PLAN: [
                CallbackQueryHandler(show_plan_confirmation, pattern=r'^select_plan_\d+$'),
                CallbackQueryHandler(show_payment_method_selection, pattern='^confirm_purchase$'),
                CallbackQueryHandler(set_cust_username_start, pattern='^set_cust_username_start$'),
                CallbackQueryHandler(apply_discount_start, pattern='^apply_discount_start$'),
                CallbackQueryHandler(start_purchase_flow, pattern='^buy_config_main$'),
            ],
            SELECT_PAYMENT_METHOD: [
                CallbackQueryHandler(pay_method_wallet, pattern=r'^pay_method_wallet$'),
                CallbackQueryHandler(show_payment_info_card, pattern=r'^pay_method_card$'),
                CallbackQueryHandler(show_payment_info_crypto, pattern=r'^pay_method_crypto$'),
                CallbackQueryHandler(show_payment_info_gateway, pattern=r'^pay_method_gateway$'),
                CallbackQueryHandler(start_purchase_flow, pattern='^buy_config_main$'),
            ],
            AWAIT_DISCOUNT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_and_validate_discount_code)],
            AWAIT_CUSTOM_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_custom_username)],
            AWAIT_PAYMENT_SCREENSHOT: [MessageHandler(filters.PHOTO | filters.Document.ALL | filters.TEXT, receive_payment_screenshot)],
        },
        fallbacks=[],
        allow_reentry=True,
        per_message=False,
    )

    renewal_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_renewal_flow, pattern=r'^renew_service_\d+$')],
        states={
            RENEW_SELECT_PLAN: [
                CallbackQueryHandler(show_renewal_plan_confirmation, pattern=r'^renew_select_plan_\d+$'),
                CallbackQueryHandler(show_payment_method_selection, pattern=r'^renew_confirm_purchase$'),
                CallbackQueryHandler(renew_apply_discount_start, pattern=r'renew_apply_discount_start'),
            ],
            SELECT_PAYMENT_METHOD: [
                CallbackQueryHandler(pay_method_wallet, pattern=r'^pay_method_wallet$'),
                CallbackQueryHandler(show_payment_info_card, pattern=r'^pay_method_card$'),
                CallbackQueryHandler(show_payment_info_crypto, pattern=r'^pay_method_crypto$'),
                CallbackQueryHandler(show_payment_info_gateway, pattern=r'^pay_method_gateway$'),
            ],
            RENEW_AWAIT_DISCOUNT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_and_validate_discount_code)],
            RENEW_AWAIT_PAYMENT: [MessageHandler(filters.PHOTO | filters.Document.ALL, receive_renewal_payment)],
        },
        fallbacks=[CallbackQueryHandler(show_specific_service_details, pattern=r'^view_service_')],
        allow_reentry=True,
        per_message=False,
    )

    application.add_handler(admin_conv, group=1)
    application.add_handler(purchase_conv, group=1)
    application.add_handler(renewal_conv, group=1)

    application.add_handler(CommandHandler('start', start_command), group=3)
    
    # Version check command
    async def version_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            import os
            version_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'VERSION.txt')
            if os.path.exists(version_file):
                with open(version_file, 'r', encoding='utf-8') as f:
                    version_info = f.read()
                await update.message.reply_text(f"📦 **نسخه ربات:**\n\n{version_info}", parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text("📦 نسخه: نامشخص")
        except Exception as e:
            await update.message.reply_text(f"خطا در خواندن نسخه: {str(e)}")
    
    application.add_handler(CommandHandler('version', version_command), group=3)

    # Admin approval callbacks
    application.add_handler(CallbackQueryHandler(admin_ask_panel_for_approval, pattern=r'^approve_auto_'), group=3)
    application.add_handler(CallbackQueryHandler(admin_approve_on_panel, pattern=r'^approve_on_panel_'), group=3)
    application.add_handler(CallbackQueryHandler(admin_review_order_reject, pattern=r'^reject_order_'), group=3)
    application.add_handler(CallbackQueryHandler(admin_manual_send_start, pattern=r'^approve_manual_'), group=3)
    # User service actions
    application.add_handler(CallbackQueryHandler(view_service_qr, pattern=r'^view_service_qr_\d+$'), group=2)
    application.add_handler(CallbackQueryHandler(refresh_service_link, pattern=r'^refresh_service_link_\d+$'), group=2)
    application.add_handler(CallbackQueryHandler(revoke_key, pattern=r'^revoke_key_\d+$'), group=2)
    application.add_handler(CallbackQueryHandler(delete_service_start, pattern=r'^delete_service_\d+$'), group=2)
    application.add_handler(CallbackQueryHandler(delete_service_confirm, pattern=r'^delete_service_(yes|no)_\d+$'), group=2)
    application.add_handler(CallbackQueryHandler(admin_approve_renewal, pattern=r'^approve_renewal_'), group=3)
    application.add_handler(CallbackQueryHandler(get_free_config_handler, pattern=r'^get_free_config$'), group=3)
    # Noop handler for display-only buttons
    async def noop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
    application.add_handler(CallbackQueryHandler(noop_handler, pattern=r'^noop$'), group=3)
    application.add_handler(CallbackQueryHandler(my_services_handler, pattern=r'^my_services(_page_\d+)?$'), group=3)
    application.add_handler(CallbackQueryHandler(wallet_menu, pattern=r'^wallet_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(support_menu, pattern=r'^support_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(show_specific_service_details, pattern=r'^view_service_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(check_service_status, pattern=r'^check_service_status_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(refresh_service_link, pattern=r'^refresh_service_link_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(view_service_qr, pattern=r'^view_service_qr_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(revoke_key, pattern=r'^revoke_key_'), group=3)
    # Fallback: allow username prompt button to work even if state dropped
    application.add_handler(CallbackQueryHandler(set_cust_username_start, pattern=r'^set_cust_username_start$'), group=3)
    application.add_handler(CallbackQueryHandler(start_command, pattern='^start_main$'), group=3)
    # Cancel flow handlers - work from anywhere
    application.add_handler(CallbackQueryHandler(cancel_flow, pattern='^cancel_flow$'), group=3)
    application.add_handler(CallbackQueryHandler(cancel_admin_flow, pattern='^cancel_admin_flow$'), group=3)
    # Ensure Admin Stats button works globally even if conversation state dropped
    application.add_handler(CallbackQueryHandler(admin_command, pattern='^admin_main$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_stats_menu, pattern='^admin_stats$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_stats_refresh, pattern='^stats_refresh$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_xui_choose_inbound, pattern=r'^xui_inbound_'), group=3)
    application.add_handler(CallbackQueryHandler(admin_wallets_menu, pattern='^admin_wallets_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_settings_manage, pattern='^admin_settings_manage$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_toggle_bot_active, pattern='^admin_toggle_bot_active$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_admins_menu, pattern='^admin_admins_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_plan_manage, pattern='^admin_plan_manage$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_plan_add_start, pattern='^plan_add$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_plan_delete, pattern=r'^plan_delete_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_plan_edit_start, pattern=r'^plan_edit_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_panels_menu, pattern='^admin_panels_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_panel_delete, pattern=r'^panel_delete_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_panel_add_start, pattern='^panel_add_start$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_panel_toggle_enabled, pattern=r'^panel_toggle_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_panel_health_check, pattern=r'^panel_health_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_panel_inbounds_menu, pattern=r'^panel_inbounds_\d+$'), group=3)
    # Admin menu buttons (orders, users, payments)
    application.add_handler(CallbackQueryHandler(admin_orders_manage, pattern='^admin_orders_manage$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_orders_manage, pattern='^admin_orders_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_orders_pending, pattern='^admin_orders_pending$'), group=3)
    application.add_handler(CallbackQueryHandler(lambda u, c: admin_orders_menu(u, c, int(u.callback_query.data.split('_')[-1])), pattern=r'^admin_orders_page_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_user_management, pattern='^admin_user_management$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_payments_menu, pattern='^admin_payments_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_system_health, pattern='^admin_system_health$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_clear_notifications, pattern='^admin_clear_notifications$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_quick_backup, pattern='^admin_quick_backup$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_discount_menu, pattern='^admin_discount_menu$'), group=3)
    # admin_messages_menu is handled by ConversationHandler, no need for global handler
    application.add_handler(CallbackQueryHandler(admin_tickets_menu, pattern='^admin_tickets_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_run_alerts_now, pattern='^run_alerts_now$'), group=3)
    # Reseller approvals (global)
    application.add_handler(CallbackQueryHandler(admin_reseller_approve, pattern=r'^reseller_approve_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_reseller_reject, pattern=r'^reseller_reject_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_reseller_menu, pattern='^admin_reseller_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_reseller_delete_start, pattern=r'^admin_reseller_delete_start$'), group=3)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_reseller_delete_receive), group=-2)
    # Reseller user flows
    application.add_handler(CallbackQueryHandler(reseller_menu, pattern=r'^reseller_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(reseller_pay_start, pattern=r'^reseller_pay_start$'), group=3)
    application.add_handler(CallbackQueryHandler(reseller_pay_card, pattern=r'^reseller_pay_card$'), group=3)
    application.add_handler(CallbackQueryHandler(reseller_pay_crypto, pattern=r'^reseller_pay_crypto$'), group=3)
    application.add_handler(CallbackQueryHandler(reseller_pay_gateway, pattern=r'^reseller_pay_gateway$'), group=3)
    application.add_handler(CallbackQueryHandler(reseller_verify_gateway, pattern=r'^reseller_verify_gateway$'), group=3)
    application.add_handler(CallbackQueryHandler(reseller_upload_start_card, pattern=r'^reseller_upload_start_card$'), group=3)
    application.add_handler(CallbackQueryHandler(reseller_upload_start_crypto, pattern=r'^reseller_upload_start_crypto$'), group=3)

    # Route critical admin callbacks globally so buttons work from any state
    # application.add_handler(CallbackQueryHandler(admin_global_router, pattern=r'^admin_'), group=0)
    application.add_handler(CommandHandler('addadmin', admin_add_command), group=0)
    application.add_handler(CommandHandler('deladmin', admin_del_command), group=0)
    application.add_handler(CommandHandler('setms', admin_setms_command), group=0)

    # Global settings callbacks so they work from any screen
    application.add_handler(CallbackQueryHandler(admin_settings_manage, pattern='^admin_settings_manage$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_settings_ask, pattern=r'^set_(trial_days|payment_text)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_toggle_trial_status, pattern=r'^set_trial_status_(0|1)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_set_usd_rate_start, pattern='^set_usd_rate_start$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_toggle_usd_mode, pattern=r'^toggle_usd_mode_(manual|api)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_toggle_pay_card, pattern=r'^toggle_pay_card_(0|1)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_toggle_pay_crypto, pattern=r'^toggle_pay_crypto_(0|1)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_toggle_pay_gateway, pattern=r'^toggle_pay_gateway_(0|1)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_toggle_gateway_type, pattern=r'^toggle_gateway_type_(zarinpal|aghapay)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_toggle_signup_bonus, pattern=r'^toggle_signup_bonus_(0|1)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_set_signup_bonus_amount_start, pattern='^set_signup_bonus_amount$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_set_trial_inbound_start, pattern='^set_trial_inbound_start$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_set_trial_inbound_choose, pattern=r'^set_trial_inbound_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_set_ref_percent_start, pattern='^set_ref_percent_start$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_set_config_footer_start, pattern='^set_config_footer_start$'), group=3)
    # Alerts & Auto-backup (global)
    application.add_handler(CallbackQueryHandler(admin_toggle_user_quota, pattern=r'^toggle_user_quota_(0|1)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_toggle_talert, pattern=r'^toggle_talert_(0|1)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_set_talert_gb_start, pattern='^set_talert_gb_start$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_toggle_time_alert, pattern=r'^toggle_time_alert_(0|1)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_set_time_alert_days_start, pattern='^set_time_alert_days_start$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_toggle_auto_backup, pattern=r'^toggle_auto_backup_(0|1)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_set_auto_backup_hours_start, pattern='^set_auto_backup_hours_start$'), group=3)

    # Wallet manual adjust (global)
    application.add_handler(CallbackQueryHandler(admin_wallet_adjust_start, pattern=r'^wallet_adjust_start_(credit|debit)$'), group=3)

    # Join/purchase logs settings (global)
    application.add_handler(CallbackQueryHandler(admin_toggle_join_logs, pattern=r'^toggle_join_logs_(0|1)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_set_join_logs_chat_start, pattern=r'^set_join_logs_chat$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_toggle_purchase_logs, pattern=r'^toggle_purchase_logs_(0|1)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_set_purchase_logs_chat_start, pattern=r'^set_purchase_logs_chat$'), group=3)

    # Text handlers for settings flows (awaiting_admin flags)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_ref_percent_save), group=-2)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_config_footer_save), group=-2)
    application.add_handler(CallbackQueryHandler(admin_set_payment_text_start, pattern='^set_payment_text$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_set_usd_rate_start_global, pattern='^set_usd_rate_start$'), group=3)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_settings_save_payment_text), group=-2)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_usd_rate_save), group=-2)
    # Text handler to capture chat IDs for logging settings
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_settings_save_log_chat), group=-2)

    # Tutorials (admin) handlers
    application.add_handler(CallbackQueryHandler(admin_tutorial_add_start, pattern='^tutorial_add_start$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_tutorial_delete, pattern=r'^tutorial_delete_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_tutorial_view, pattern=r'^tutorial_view_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_tutorials_menu, pattern='^admin_tutorials_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_tutorial_finish, pattern='^tutorial_finish$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_tutorial_media_page, pattern=r'^tutorial_media_page_(prev|next)$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_tutorial_edit_title_start, pattern='^tutorial_edit_title$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_tutorial_media_delete, pattern=r'^tmedia_del_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_tutorial_media_move, pattern=r'^tmedia_(up|down)_\d+$'), group=3)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_tutorial_receive_title), group=-3)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, admin_tutorial_receive_media), group=-3)


    async def check_join_and_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Verify membership before proceeding
        from .config import CHANNEL_ID as _CID, CHANNEL_USERNAME as _CUN, logger as _logger
        try:
            from .config import CHANNEL_CHAT as _CHAT
        except Exception:
            _CHAT = None
        chat_id = _CHAT if _CHAT is not None else (_CID or _CUN)
        is_member = False
        try:
            member = await context.bot.get_chat_member(chat_id=chat_id, user_id=update.effective_user.id)
            if getattr(member, 'status', None) in ['member', 'administrator', 'creator']:
                is_member = True
        except Exception as e:
            # If cannot verify, treat as not joined to avoid bypass
            try:
                _logger.warning(f"check_join_and_start: membership check failed for {update.effective_user.id}: {e}")
            except Exception:
                pass
            is_member = False

        if not is_member:
            # Rebuild join gate UI
            join_url = None
            channel_hint = ""
            try:
                chat_obj = await context.bot.get_chat(chat_id=chat_id)
                uname = getattr(chat_obj, 'username', None)
                inv = getattr(chat_obj, 'invite_link', None)
                if uname:
                    handle = f"@{str(uname).replace('@','')}"
                    join_url = f"https://t.me/{str(uname).replace('@','')}"
                    channel_hint = f"\n\nکانال: {handle}"
                elif inv:
                    join_url = inv
                    channel_hint = "\n\nلینک دعوت کانال در دکمه زیر موجود است."
            except Exception:
                if (_CUN or '').strip():
                    handle = (_CUN or '').strip()
                    if not handle.startswith('@'):
                        handle = f"@{handle}"
                    join_url = f"https://t.me/{handle.replace('@','')}"
                    channel_hint = f"\n\nکانال: {handle}"
                elif _CID:
                    channel_hint = f"\n\nشناسه کانال: `{_CID}`"

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            from telegram.constants import ParseMode
            kb = []
            if join_url:
                kb.append([InlineKeyboardButton("\U0001F195 عضویت در کانال", url=join_url)])
            kb.append([InlineKeyboardButton("\u2705 عضو شدم", callback_data='check_join')])
            text = (
                f"\u26A0\uFE0F **قفل عضویت**\n\nبرای استفاده از ربات، ابتدا در کانال ما عضو شوید و سپس دکمه «عضو شدم» را بزنید." + channel_hint
            )
            try:
                if update.callback_query and update.callback_query.message:
                    await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
                    await update.callback_query.answer("ابتدا عضو کانال شوید و دوباره تلاش کنید.", show_alert=True)
                else:
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass
            return

        await register_new_user(update.effective_user, update, referrer_hint=context.user_data.get('referrer_id'))
        await start_command(update, context)

    application.add_handler(CallbackQueryHandler(check_join_and_start, pattern='^check_join$'), group=3)

    application.add_handler(CallbackQueryHandler(dynamic_button_handler), group=4)

    # User main menu callbacks (global)
    application.add_handler(CallbackQueryHandler(wallet_menu, pattern=r'^wallet_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(support_menu, pattern=r'^support_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(tutorials_menu, pattern=r'^tutorials_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(tutorial_show, pattern=r'^tutorial_show_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(referral_menu, pattern=r'^referral_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(reseller_menu, pattern=r'^reseller_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(card_to_card_info, pattern=r'^card_to_card_info$'), group=3)

    # User wallet flows and support/tutorials (global callbacks)
    application.add_handler(CallbackQueryHandler(wallet_verify_gateway, pattern=r'^wallet_verify_gateway$'), group=3)

    # Unified upload router handles both wallet and reseller (run early to avoid other catch-alls)
    application.add_handler(MessageHandler(filters.PHOTO | filters.VOICE | filters.VIDEO | filters.AUDIO | filters.Document.ALL | filters.TEXT, composite_upload_router), group=0)

    # Reseller flows
    application.add_handler(CallbackQueryHandler(reseller_pay_start, pattern=r'^reseller_pay_start$'), group=3)
    application.add_handler(CallbackQueryHandler(reseller_pay_card, pattern=r'^reseller_pay_card$'), group=3)
    application.add_handler(CallbackQueryHandler(reseller_pay_crypto, pattern=r'^reseller_pay_crypto$'), group=3)
    application.add_handler(CallbackQueryHandler(reseller_pay_gateway, pattern=r'^reseller_pay_gateway$'), group=3)
    application.add_handler(CallbackQueryHandler(reseller_verify_gateway, pattern=r'^reseller_verify_gateway$'), group=3)
    application.add_handler(CallbackQueryHandler(reseller_upload_start_card, pattern=r'^reseller_upload_start_card$'), group=3)
    application.add_handler(CallbackQueryHandler(reseller_upload_start_crypto, pattern=r'^reseller_upload_start_crypto$'), group=3)
    # Already covered by composite router

    # Admin tickets (global)
    application.add_handler(CallbackQueryHandler(admin_tickets_menu, pattern=r'^admin_tickets_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_ticket_view, pattern=r'^ticket_view_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_ticket_delete, pattern=r'^ticket_delete_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_ticket_reply_start, pattern=r'^ticket_reply_\d+$'), group=3)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, admin_ticket_receive_reply), group=-3)

    # Admin wallet tx (global)
    application.add_handler(CallbackQueryHandler(admin_wallet_tx_menu, pattern=r'^admin_wallet_tx_menu$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_wallet_tx_view, pattern=r'^wallet_tx_view_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_wallet_tx_approve, pattern=r'^wallet_tx_approve_\d+$'), group=3)
    application.add_handler(CallbackQueryHandler(admin_wallet_tx_reject, pattern=r'^wallet_tx_reject_\d+$'), group=3)
    # Place before other generic text handlers to ensure it captures admin adjust flow
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_wallet_adjust_text_router), group=-4)

    admin_reply_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_ticket_reply_start, pattern=r'^ticket_reply_\d+$')],
        states={
            ADMIN_AWAIT_TICKET_REPLY: [MessageHandler(filters.ALL & ~filters.COMMAND, admin_ticket_receive_reply)],
        },
        fallbacks=[CallbackQueryHandler(admin_tickets_menu, pattern='^admin_tickets_menu$')],
        allow_reentry=True,
        per_message=False,
    )
    application.add_handler(admin_reply_conv, group=1)

    wallet_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(wallet_topup_gateway_start, pattern=r'^wallet_topup_gateway$'),
            CallbackQueryHandler(wallet_topup_card_start, pattern=r'^wallet_topup_card$'),
            CallbackQueryHandler(wallet_topup_crypto_start, pattern=r'^wallet_topup_crypto$'),
        ],
        states={
            WALLET_AWAIT_AMOUNT_GATEWAY: [
                CallbackQueryHandler(wallet_select_amount, pattern=r'^wallet_amt_gateway_\d+$'),
                CallbackQueryHandler(wallet_topup_custom_amount_start, pattern=r'^wallet_amt_gateway_custom$')
            ],
            WALLET_AWAIT_AMOUNT_CARD: [
                CallbackQueryHandler(wallet_select_amount, pattern=r'^wallet_amt_card_\d+$'),
                CallbackQueryHandler(wallet_topup_custom_amount_start, pattern=r'^wallet_amt_card_custom$')
            ],
            WALLET_AWAIT_AMOUNT_CRYPTO: [
                CallbackQueryHandler(wallet_select_amount, pattern=r'^wallet_amt_crypto_\d+$'),
                CallbackQueryHandler(wallet_topup_custom_amount_start, pattern=r'^wallet_amt_crypto_custom$')
            ],
            WALLET_AWAIT_CUSTOM_AMOUNT_GATEWAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_topup_custom_amount_receive)],
            WALLET_AWAIT_CUSTOM_AMOUNT_CARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_topup_custom_amount_receive)],
            WALLET_AWAIT_CUSTOM_AMOUNT_CRYPTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_topup_custom_amount_receive)],
            WALLET_AWAIT_CARD_SCREENSHOT: [
                CallbackQueryHandler(wallet_upload_start_card, pattern=r'^wallet_upload_start_card$'),
                CallbackQueryHandler(wallet_upload_start_crypto, pattern=r'^wallet_upload_start_crypto$'),
                MessageHandler(filters.ALL & ~filters.COMMAND, composite_upload_router)
            ],
        },
        fallbacks=[CallbackQueryHandler(wallet_menu, pattern='^wallet_menu$')],
        allow_reentry=True,
        per_message=False,
    )
    application.add_handler(wallet_conv, group=1)

    support_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ticket_create_start, pattern=r'^ticket_create_start$')],
        states={
            SUPPORT_AWAIT_TICKET: [MessageHandler(filters.ALL & ~filters.COMMAND, ticket_receive_message)],
        },
        fallbacks=[],
        allow_reentry=True,
        per_message=False,
    )

    application.add_handler(support_conv, group=1)

    return application


def run(token: str | None = None):
    if not token:
        from .config import BOT_TOKEN as _TB
        token = _TB

    use_webhook = (os.getenv('USE_WEBHOOK') or '').lower() in ('1', 'true', 'yes')

    # Proactively clear old webhook to avoid event-loop race and drop stale updates
    try:
        requests.post(
            f'https://api.telegram.org/bot{token}/deleteWebhook',
            params={'drop_pending_updates': 'true'},
            timeout=5,
        )
    except Exception:
        pass

    app = build_application()

    if not use_webhook:
        # Long polling mode (recommended for VPS/server)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(app.bot.delete_webhook(drop_pending_updates=True))
            else:
                loop.run_until_complete(app.bot.delete_webhook(drop_pending_updates=True))
        except Exception:
            pass
        app.run_polling(drop_pending_updates=True)
        return

    # Webhook mode (for shared hosting with HTTPS domain + open HTTP port)
    listen_addr = os.getenv('WEBHOOK_LISTEN', '0.0.0.0')
    listen_port = int(os.getenv('WEBHOOK_PORT', '8080'))
    url_path = os.getenv('WEBHOOK_PATH', token)
    base_url = (os.getenv('WEBHOOK_URL') or '').strip()
    secret_token = os.getenv('WEBHOOK_SECRET')

    # If WEBHOOK_URL not set or invalid, fallback to polling to keep bot usable
    if not (base_url.startswith('http://') or base_url.startswith('https://')):
        app.run_polling(drop_pending_updates=True)
        return

    # Drop any pending updates before switching to webhook
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(app.bot.delete_webhook(drop_pending_updates=True))
        else:
            loop.run_until_complete(app.bot.delete_webhook(drop_pending_updates=True))
    except Exception:
        pass

    webhook_url = f"{base_url.rstrip('/')}/{url_path.lstrip('/')}"
    app.run_webhook(
        listen=listen_addr,
        port=listen_port,
        url_path=url_path,
        webhook_url=webhook_url,
        secret_token=secret_token,
    )