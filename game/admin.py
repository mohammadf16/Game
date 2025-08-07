from django.contrib import admin
from .models import (
    Question, DecoyQuestion, GameRoom, Player, 
    GameRound, PlayerAnswer, Vote, GameEvent
)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text', 'category', 'difficulty', 'min_answer', 'max_answer', 'is_active']
    list_filter = ['category', 'difficulty', 'is_active']
    search_fields = ['text']
    list_editable = ['is_active']


@admin.register(DecoyQuestion)
class DecoyQuestionAdmin(admin.ModelAdmin):
    list_display = ['text', 'min_answer', 'max_answer', 'is_active']
    list_filter = ['is_active']
    search_fields = ['text']
    list_editable = ['is_active']


@admin.register(GameRoom)
class GameRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'host', 'status', 'player_count', 'current_round', 'total_rounds', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'host__username']
    readonly_fields = ['id', 'created_at', 'started_at', 'finished_at']


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['nickname', 'room', 'user', 'score', 'is_connected', 'joined_at']
    list_filter = ['is_connected', 'joined_at']
    search_fields = ['nickname', 'user__username', 'room__name']


@admin.register(GameRound)
class GameRoundAdmin(admin.ModelAdmin):
    list_display = ['room', 'round_number', 'question', 'imposter', 'status', 'started_at']
    list_filter = ['status', 'started_at']
    search_fields = ['room__name', 'question__text']


@admin.register(PlayerAnswer)
class PlayerAnswerAdmin(admin.ModelAdmin):
    list_display = ['player', 'round', 'answer', 'submitted_at']
    list_filter = ['submitted_at']
    search_fields = ['player__nickname', 'round__room__name']


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['voter', 'accused', 'round', 'submitted_at']
    list_filter = ['submitted_at']
    search_fields = ['voter__nickname', 'accused__nickname']


@admin.register(GameEvent)
class GameEventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'room', 'player', 'timestamp']
    list_filter = ['event_type', 'timestamp']
    search_fields = ['room__name', 'player__nickname']
    readonly_fields = ['timestamp']
