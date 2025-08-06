from django.urls import path
from . import views

app_name = 'game'

urlpatterns = [
    # Authentication
    path('api/auth/register/', views.register_user, name='register_user'),
    path('api/auth/login/', views.login_user, name='login_user'),
    path('api/auth/logout/', views.logout_user, name='logout_user'),
    path('api/auth/profile/', views.get_user_profile, name='get_user_profile'),
    path('api/auth/profile/update/', views.update_user_profile, name='update_user_profile'),
    path('api/auth/check-reconnection/', views.check_reconnection, name='check_reconnection'),
    
    # Room management
    path('api/rooms/', views.list_rooms, name='list_rooms'),
    path('api/rooms/user/', views.get_user_rooms, name='get_user_rooms'),
    path('api/rooms/create/', views.create_room, name='create_room'),
    path('api/rooms/join-by-code/', views.join_room_by_code, name='join_room_by_code'),
    path('api/rooms/<uuid:room_id>/', views.get_room, name='get_room'),
    path('api/rooms/<uuid:room_id>/join/', views.join_room, name='join_room'),
    path('api/rooms/<uuid:room_id>/leave/', views.leave_room, name='leave_room'),
    path('api/rooms/<uuid:room_id>/start/', views.start_game, name='start_game'),
    path('api/rooms/<uuid:room_id>/activity/', views.update_activity, name='update_activity'),
    
    # Game flow
    path('api/rooms/<uuid:room_id>/current-round/', views.get_current_round, name='get_current_round'),
    path('api/rooms/<uuid:room_id>/submit-answer/', views.submit_answer, name='submit_answer'),
    path('api/rooms/<uuid:room_id>/start-voting/', views.start_voting, name='start_voting'),
    path('api/rooms/<uuid:room_id>/submit-vote/', views.submit_vote, name='submit_vote'),
    path('api/rooms/<uuid:room_id>/results/', views.get_round_results, name='get_round_results'),
    path('api/rooms/<uuid:room_id>/continue/', views.continue_to_next_round, name='continue_to_next_round'),
    path('api/rooms/<uuid:room_id>/events/', views.get_game_events, name='get_game_events'),
    
    # Admin API endpoints (temporarily disabled until implemented)
    # path('api/admin/overview/', views.admin_overview, name='admin_overview'),
    # path('api/admin/players/', views.admin_players, name='admin_players'),
    # path('api/admin/games/', views.admin_games, name='admin_games'),
    # path('api/admin/stats/', views.admin_stats, name='admin_stats'),
    # path('api/admin/system-info/', views.admin_system_info, name='admin_system_info'),
    # path('api/admin/cleanup/', views.admin_system_cleanup, name='admin_system_cleanup'),
    # path('api/admin/player/<int:player_id>/', views.admin_player_detail, name='admin_player_detail'),
    # path('api/admin/game/<int:game_id>/', views.admin_game_detail, name='admin_game_detail'),
    path('api/admin/cleanup-sessions/', views.cleanup_old_sessions, name='cleanup_old_sessions'),
    path('api/admin/cleanup-games/', views.cleanup_finished_games, name='cleanup_finished_games'),
    
    # Room management
    path('api/rooms/<uuid:room_id>/close/', views.close_room, name='close_room'),
    path('api/rooms/<uuid:room_id>/delete/', views.delete_room, name='delete_room'),
    
    # Statistics and Leaderboard
    path('api/stats/history/', views.get_user_game_history, name='get_user_game_history'),
    path('api/leaderboard/', views.get_leaderboard, name='get_leaderboard'),
]