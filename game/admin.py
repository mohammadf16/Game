from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Question, DecoyQuestion, GameRoom, Player, 
    GameRound, PlayerAnswer, Vote, GameEvent, PlayerGameStats,
    UserSession, Leaderboard
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'total_games', 'total_wins', 'total_score', 'is_active', 'last_active']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'date_joined', 'last_active']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['-date_joined']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Game Statistics', {
            'fields': ('total_games', 'total_wins', 'total_imposter_wins', 'total_detective_wins', 'total_score', 'avatar')
        }),
        ('Activity', {
            'fields': ('created_at', 'last_active')
        }),
    )
    readonly_fields = ['created_at', 'last_active']


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text_preview', 'category', 'difficulty', 'min_answer', 'max_answer', 'is_active', 'created_at']
    list_filter = ['category', 'difficulty', 'is_active', 'created_at']
    search_fields = ['text']
    list_editable = ['is_active']
    ordering = ['category', 'difficulty', 'created_at']
    
    def text_preview(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Question Text'


@admin.register(DecoyQuestion)
class DecoyQuestionAdmin(admin.ModelAdmin):
    list_display = ['text_preview', 'min_answer', 'max_answer', 'is_active']
    list_filter = ['is_active']
    search_fields = ['text']
    list_editable = ['is_active']
    
    def text_preview(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Question Text'


@admin.register(GameRoom)
class GameRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'host', 'status', 'player_count_display', 'current_round', 'total_rounds', 'is_private', 'created_at']
    list_filter = ['status', 'is_private', 'created_at', 'started_at', 'finished_at']
    search_fields = ['name', 'host__username', 'room_code']
    readonly_fields = ['id', 'created_at', 'started_at', 'finished_at', 'player_count_display']
    
    def player_count_display(self, obj):
        return f"{obj.player_count}/{obj.max_players}"
    player_count_display.short_description = 'Players'


class PlayerGameStatsInline(admin.TabularInline):
    model = PlayerGameStats
    extra = 0
    readonly_fields = ['created_at']


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['nickname', 'user', 'room', 'score', 'is_connected', 'joined_at', 'last_active']
    list_filter = ['is_connected', 'joined_at', 'last_active']
    search_fields = ['nickname', 'user__username', 'room__name']
    readonly_fields = ['joined_at', 'last_active']
    inlines = [PlayerGameStatsInline]


@admin.register(GameRound)
class GameRoundAdmin(admin.ModelAdmin):
    list_display = ['room', 'round_number', 'question_preview', 'imposter', 'status', 'started_at', 'finished_at']
    list_filter = ['status', 'started_at', 'finished_at']
    search_fields = ['room__name', 'question__text', 'imposter__nickname']
    readonly_fields = ['started_at', 'discussion_started_at', 'voting_started_at', 'finished_at']
    
    def question_preview(self, obj):
        return obj.question.text[:30] + "..." if len(obj.question.text) > 30 else obj.question.text
    question_preview.short_description = 'Question'


@admin.register(PlayerAnswer)
class PlayerAnswerAdmin(admin.ModelAdmin):
    list_display = ['player', 'round_info', 'answer', 'submitted_at']
    list_filter = ['submitted_at', 'round__status']
    search_fields = ['player__nickname', 'round__room__name']
    readonly_fields = ['submitted_at']
    
    def round_info(self, obj):
        return f"{obj.round.room.name} - Round {obj.round.round_number}"
    round_info.short_description = 'Round'


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['voter', 'accused', 'round_info', 'submitted_at']
    list_filter = ['submitted_at']
    search_fields = ['voter__nickname', 'accused__nickname', 'round__room__name']
    readonly_fields = ['submitted_at']
    
    def round_info(self, obj):
        return f"{obj.round.room.name} - Round {obj.round.round_number}"
    round_info.short_description = 'Round'


@admin.register(PlayerGameStats)
class PlayerGameStatsAdmin(admin.ModelAdmin):
    list_display = ['player', 'room', 'round_number', 'role', 'result', 'points_earned', 'was_voted_out', 'created_at']
    list_filter = ['role', 'result', 'was_voted_out', 'created_at']
    search_fields = ['player__nickname', 'room__name']
    readonly_fields = ['created_at']


@admin.register(GameEvent)
class GameEventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'room', 'player', 'timestamp']
    list_filter = ['event_type', 'timestamp']
    search_fields = ['room__name', 'player__nickname']
    readonly_fields = ['timestamp']
    
    def has_change_permission(self, request, obj=None):
        return False  # Events should not be editable
    
    def has_add_permission(self, request):
        return False  # Events are created automatically


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'current_room', 'last_activity', 'created_at']
    list_filter = ['last_activity', 'created_at']
    search_fields = ['user__username', 'current_room__name']
    readonly_fields = ['session_key', 'created_at', 'last_activity']


@admin.register(Leaderboard)
class LeaderboardAdmin(admin.ModelAdmin):
    list_display = ['user', 'period', 'rank', 'total_score', 'total_wins', 'total_games', 'win_rate_display', 'updated_at']
    list_filter = ['period', 'rank', 'updated_at']
    search_fields = ['user__username']
    readonly_fields = ['created_at', 'updated_at', 'win_rate_display']
    ordering = ['period', 'rank']
    
    def win_rate_display(self, obj):
        return f"{obj.win_rate:.1f}%"
    win_rate_display.short_description = 'Win Rate'
    
    def has_add_permission(self, request):
        return False  # Leaderboards are generated automatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Leaderboards are updated automatically


# Custom admin site configuration
admin.site.site_header = "Number Hunt Administration"
admin.site.site_title = "Number Hunt Admin"
admin.site.index_title = "Welcome to Number Hunt Administration"


# Add some custom admin actions
@admin.action(description='Reset user game statistics')
def reset_user_stats(modeladmin, request, queryset):
    """Reset selected users' game statistics"""
    for user in queryset:
        user.total_games = 0
        user.total_wins = 0
        user.total_imposter_wins = 0
        user.total_detective_wins = 0
        user.total_score = 0
        user.save()
    
    modeladmin.message_user(request, f"Reset statistics for {queryset.count()} users.")


@admin.action(description='Mark selected players as connected')
def mark_players_connected(modeladmin, request, queryset):
    """Mark selected players as connected"""
    queryset.update(is_connected=True)
    modeladmin.message_user(request, f"Marked {queryset.count()} players as connected.")


@admin.action(description='Mark selected players as disconnected')
def mark_players_disconnected(modeladmin, request, queryset):
    """Mark selected players as disconnected"""
    queryset.update(is_connected=False)
    modeladmin.message_user(request, f"Marked {queryset.count()} players as disconnected.")


# Add actions to respective admin classes
UserAdmin.actions = [reset_user_stats]
PlayerAdmin.actions = [mark_players_connected, mark_players_disconnected]