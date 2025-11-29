"""Admin panel handlers"""

from .admin import (
    admin_command,
    admin_toggle_bot_active,
    admin_approve_on_panel,
    admin_xui_choose_inbound,
    admin_review_order_reject,
    admin_approve_renewal,
    admin_manual_send_start,
    process_manual_order_message,
    admin_send_by_id_start,
    process_send_by_id_get_id,
    process_send_by_id_get_message,
    admin_run_reminder_check,
    admin_set_trial_inbound_start,
    admin_set_trial_inbound_choose,
    backup_restore_start,
    backup_restore_receive_file
)

from .admin_users import (
    admin_users_menu,
    admin_users_page,
    admin_users_search_start,
    admin_users_search_apply,
    admin_users_toggle_ban,
    admin_users_export_csv,
    admin_users_view_by_id_start,
    admin_users_view_by_id_show,
    admin_users_toggle_ban_inline,
    admin_users_show_services,
    admin_users_show_tickets,
    admin_users_show_wallet,
    admin_users_show_refs
)

from .admin_system import (
    admin_system_health,
    admin_clear_notifications
)

# Export all admin handlers
__all__ = [
    'admin_command',
    'admin_toggle_bot_active',
    'admin_approve_on_panel',
    'admin_xui_choose_inbound',
    'admin_review_order_reject',
    'admin_approve_renewal',
    'admin_manual_send_start',
    'process_manual_order_message',
    'admin_send_by_id_start',
    'process_send_by_id_get_id',
    'process_send_by_id_get_message',
    'admin_run_reminder_check',
    'admin_set_trial_inbound_start',
    'admin_set_trial_inbound_choose',
    'backup_restore_start',
    'backup_restore_receive_file',
    'admin_users_menu',
    'admin_users_page',
    'admin_users_search_start',
    'admin_users_search_apply',
    'admin_users_toggle_ban',
    'admin_users_export_csv',
    'admin_users_view_by_id_start',
    'admin_users_view_by_id_show',
    'admin_users_toggle_ban_inline',
    'admin_users_show_services',
    'admin_users_show_tickets',
    'admin_users_show_wallet',
    'admin_users_show_refs',
    'admin_system_health',
    'admin_clear_notifications'
]
