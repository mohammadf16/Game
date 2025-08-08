from django.urls import path
from . import views

app_name = 'game'

urlpatterns = [
    # User management
    path('api/create-user/', views.create_user, name='create_user'),
    
    # Room management
    path('api/rooms/', views.list_rooms, name='list_rooms'),
    path('api/rooms/create/', views.create_room, name='create_room'),
    path('api/rooms/<uuid:room_id>/', views.get_room, name='get_room'),
    path('api/rooms/<uuid:room_id>/join/', views.join_room, name='join_room'),
    path('api/rooms/<uuid:room_id>/start/', views.start_game, name='start_game'),
    
    # Game flow
    path('api/rooms/<uuid:room_id>/current-round/', views.get_current_round, name='get_current_round'),
    path('api/rooms/<uuid:room_id>/submit-answer/', views.submit_answer, name='submit_answer'),
    path('api/rooms/<uuid:room_id>/start-voting/', views.start_voting, name='start_voting'),
    path('api/rooms/<uuid:room_id>/submit-vote/', views.submit_vote, name='submit_vote'),
    path('api/rooms/<uuid:room_id>/results/', views.get_round_results, name='get_round_results'),
    path('api/rooms/<uuid:room_id>/continue/', views.continue_to_next_round, name='continue_to_next_round'),
    path('api/rooms/<uuid:room_id>/events/', views.get_game_events, name='get_game_events'),
]
