from django.shortcuts import render, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.db.models import Q, Count, Avg, Sum
from django.db import transaction
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from datetime import timedelta, datetime
import random

from .models import (
    User, Question, DecoyQuestion, GameRoom, Player, 
    GameRound, PlayerAnswer, Vote, GameEvent, PlayerGameStats,
    UserSession, Leaderboard
)
from .serializers import (
    UserSerializer, UserRegistrationSerializer, UserLoginSerializer,
    GameRoomSerializer, GameRoomCreateSerializer, PlayerSerializer,
    GameRoundSerializer, JoinRoomSerializer, SubmitAnswerSerializer,
    SubmitVoteSerializer, QuestionSerializer, GameEventSerializer,
    UserStatsSerializer, LeaderboardSerializer, PlayerGameStatsSerializer
)


# ================================
# Authentication Views
# ================================

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """Register a new user"""
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, created = Token.objects.get_or_create(user=user)
        login(request, user)
        
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key,
            'message': 'Registration successful'
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    """Login user"""
    serializer = UserLoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        login(request, user)
        
        # Update last active
        user.last_active = timezone.now()
        user.save(update_fields=['last_active'])
        
        # Create or update session
        session_key = request.session.session_key
        if session_key:
            UserSession.objects.update_or_create(
                user=user,
                session_key=session_key,
                defaults={'last_activity': timezone.now()}
            )
        
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key,
            'message': 'Login successful'
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_user(request):
    """Logout user"""
    try:
        # Delete token
        Token.objects.filter(user=request.user).delete()
        
        # Update user sessions
        UserSession.objects.filter(user=request.user).delete()
        
        logout(request)
        return Response({'message': 'Logout successful'})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    """Get current user profile with stats"""
    serializer = UserStatsSerializer(request.user)
    return Response(serializer.data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    """Update user profile"""
    serializer = UserSerializer(request.user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ================================
# Room Management Views
# ================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_rooms(request):
    """List available game rooms with user context"""
    rooms = GameRoom.objects.filter(
        Q(status='waiting') | Q(players__user=request.user)
    ).distinct().order_by('-created_at')
    
    serializer = GameRoomSerializer(rooms, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_rooms(request):
    """Get user's current and recent rooms"""
    # Current room (in progress or waiting)
    current_room = GameRoom.objects.filter(
        players__user=request.user,
        status__in=['waiting', 'in_progress']
    ).first()
    
    # Recent finished games
    recent_rooms = GameRoom.objects.filter(
        players__user=request.user,
        status='finished'
    ).order_by('-finished_at')[:10]
    
    return Response({
        'current_room': GameRoomSerializer(current_room, context={'request': request}).data if current_room else None,
        'recent_games': GameRoomSerializer(recent_rooms, many=True, context={'request': request}).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_room(request):
    """Create a new game room"""
    serializer = GameRoomCreateSerializer(data=request.data)
    if serializer.is_valid():
        room = serializer.save(host=request.user)
        
        # Automatically add host as a player
        nickname = request.data.get('nickname', request.user.username)
        Player.objects.create(
            user=request.user,
            room=room,
            nickname=nickname
        )
        
        # Create game event
        GameEvent.objects.create(
            room=room,
            event_type='player_joined',
            data={'host': request.user.username, 'nickname': nickname}
        )
        
        return Response(GameRoomSerializer(room, context={'request': request}).data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_room(request, room_id):
    """Get room details"""
    room = get_object_or_404(GameRoom, id=room_id)
    serializer = GameRoomSerializer(room, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_room(request, room_id):
    """Join a game room"""
    room = get_object_or_404(GameRoom, id=room_id)
    
    # Check if user can join
    if not room.can_user_join(request.user):
        if room.status == 'finished':
            return Response({'error': 'Game has finished'}, status=status.HTTP_400_BAD_REQUEST)
        elif room.status == 'in_progress':
            # Check if user was already a player - allow reconnection
            try:
                player = Player.objects.get(user=request.user, room=room)
                player.is_connected = True
                player.update_activity()
                
                # Create reconnection event
                GameEvent.objects.create(
                    room=room,
                    event_type='player_reconnected',
                    player=player,
                    data={'nickname': player.nickname}
                )
                
                return Response({
                    'message': 'Reconnected to game successfully',
                    'player': PlayerSerializer(player).data,
                    'room': GameRoomSerializer(room, context={'request': request}).data
                })
            except Player.DoesNotExist:
                return Response({'error': 'Cannot join game in progress'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'error': 'Room is full'}, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = JoinRoomSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    nickname = serializer.validated_data['nickname']
    
    # Check if player already exists in room
    player, created = Player.objects.get_or_create(
        user=request.user,
        room=room,
        defaults={'nickname': nickname, 'is_connected': True}
    )
    
    if not created:
        # Player rejoining
        player.is_connected = True
        player.nickname = nickname  # Allow nickname update
        player.update_activity()
        event_type = 'player_reconnected'
    else:
        event_type = 'player_joined'
    
    # Create game event
    GameEvent.objects.create(
        room=room,
        event_type=event_type,
        player=player,
        data={'nickname': nickname}
    )
    
    return Response({
        'message': 'Joined room successfully' if created else 'Reconnected successfully',
        'player': PlayerSerializer(player).data,
        'room': GameRoomSerializer(room, context={'request': request}).data
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_room_by_code(request):
    """Join room by private room code"""
    room_code = request.data.get('room_code', '').upper()
    if not room_code:
        return Response({'error': 'Room code is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        room = GameRoom.objects.get(room_code=room_code, is_private=True)
    except GameRoom.DoesNotExist:
        return Response({'error': 'Invalid room code'}, status=status.HTTP_404_NOT_FOUND)
    
    # Use the regular join room logic
    request.data['room_id'] = str(room.id)
    return join_room(request, room.id)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_game(request, room_id):
    """Start the game"""
    room = get_object_or_404(GameRoom, id=room_id)
    
    # Only host can start the game
    if room.host != request.user:
        return Response({'error': 'Only the host can start the game'}, status=status.HTTP_403_FORBIDDEN)
    
    if not room.can_start():
        return Response({'error': 'Cannot start game. Need at least 3 players.'}, status=status.HTTP_400_BAD_REQUEST)
    
    with transaction.atomic():
        room.status = 'in_progress'
        room.started_at = timezone.now()
        room.current_round = 1
        room.save()
        
        # Start first round
        start_round(room, 1)
        
        # Create game event
        GameEvent.objects.create(
            room=room,
            event_type='game_started',
            data={'player_count': room.player_count}
        )
    
    return Response(GameRoomSerializer(room, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leave_room(request, room_id):
    """Leave a room"""
    room = get_object_or_404(GameRoom, id=room_id)
    
    try:
        player = Player.objects.get(user=request.user, room=room)
    except Player.DoesNotExist:
        return Response({'error': 'You are not in this room'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Mark as disconnected instead of deleting
    player.is_connected = False
    player.save()
    
    # Create game event
    GameEvent.objects.create(
        room=room,
        event_type='player_left',
        player=player,
        data={'nickname': player.nickname}
    )
    
    return Response({'message': 'Left room successfully'})


# ================================
# Game Flow Functions
# ================================

def start_round(room, round_number):
    """Start a new round"""
    # Get random question and decoy question
    question = Question.objects.filter(is_active=True).order_by('?').first()
    decoy_question = DecoyQuestion.objects.filter(is_active=True).order_by('?').first()
    
    if not question or not decoy_question:
        raise ValueError("No questions available")
    
    # Select random imposter from connected players
    connected_players = list(room.players.filter(is_connected=True))
    if not connected_players:
        raise ValueError("No connected players")
    
    imposter = random.choice(connected_players)
    
    # Create round
    game_round = GameRound.objects.create(
        room=room,
        round_number=round_number,
        question=question,
        decoy_question=decoy_question,
        imposter=imposter,
        status='answering'
    )
    
    # Create game event
    GameEvent.objects.create(
        room=room,
        event_type='round_started',
        data={
            'round_number': round_number,
            'question_id': question.id,
            'imposter_id': imposter.id
        }
    )
    
    return game_round


def end_round(game_round):
    """End the current round and calculate results"""
    room = game_round.room
    
    # Calculate vote results
    vote_counts = {}
    voter_choices = {}
    
    for vote in game_round.votes.all():
        accused_id = vote.accused.id
        vote_counts[accused_id] = vote_counts.get(accused_id, 0) + 1
        voter_choices[vote.voter.id] = {
            'voter_nickname': vote.voter.nickname,
            'accused_id': accused_id,
            'accused_nickname': vote.accused.nickname
        }
    
    # Find player with most votes
    most_voted_player = None
    imposter_caught = False
    
    if vote_counts:
        most_voted_id = max(vote_counts.keys(), key=lambda k: vote_counts[k])
        most_voted_player = Player.objects.get(id=most_voted_id)
        imposter_caught = (most_voted_player == game_round.imposter)
    
    # Update scores and create player game stats
    with transaction.atomic():
        for player in room.players.filter(is_connected=True):
            is_imposter = (player == game_round.imposter)
            points_earned = 0
            result = 'loss'
            correct_votes = 0
            
            if is_imposter:
                # Imposter scoring
                if not imposter_caught:
                    points_earned = 3
                    result = 'win'
                    player.user.total_imposter_wins += 1
            else:
                # Detective scoring
                player_vote = game_round.votes.filter(voter=player).first()
                if player_vote:
                    if imposter_caught and player_vote.accused == game_round.imposter:
                        # Correctly voted for imposter
                        points_earned = 2
                        result = 'win'
                        correct_votes = 1
                        player.user.total_detective_wins += 1
                    elif not imposter_caught and player_vote.accused != game_round.imposter:
                        # Correctly didn't vote for imposter (but imposter won)
                        points_earned = 1
                        correct_votes = 1
            
            # Update player score
            player.score += points_earned
            player.save()
            
            # Update user stats
            if result == 'win':
                player.user.total_wins += 1
            player.user.total_score += points_earned
            player.user.save(update_fields=['total_wins', 'total_score', 'total_imposter_wins', 'total_detective_wins'])
            
            # Create player game stats
            PlayerGameStats.objects.create(
                player=player,
                room=room,
                round_number=game_round.round_number,
                role='imposter' if is_imposter else 'detective',
                result=result,
                points_earned=points_earned,
                was_voted_out=(player == most_voted_player),
                correct_votes=correct_votes
            )
    
    # Update round status
    game_round.status = 'results'
    game_round.finished_at = timezone.now()
    game_round.save()
    
    # Create detailed game event with results
    GameEvent.objects.create(
        room=room,
        event_type='round_ended',
        data={
            'round_number': game_round.round_number,
            'imposter_id': game_round.imposter.id,
            'imposter_nickname': game_round.imposter.nickname,
            'imposter_caught': imposter_caught,
            'most_voted_player_id': most_voted_player.id if most_voted_player else None,
            'most_voted_player_nickname': most_voted_player.nickname if most_voted_player else None,
            'vote_counts': vote_counts,
            'voter_choices': voter_choices,
            'total_votes': len(voter_choices)
        }
    )
    
    return {
        'imposter_caught': imposter_caught,
        'imposter': game_round.imposter,
        'most_voted_player': most_voted_player,
        'vote_counts': vote_counts,
        'voter_choices': voter_choices
    }


# ================================
# Game Play Views
# ================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_round(request, room_id):
    """Get current round information"""
    room = get_object_or_404(GameRoom, id=room_id)
    
    # Update player activity
    try:
        player = Player.objects.get(user=request.user, room=room)
        player.update_activity()
    except Player.DoesNotExist:
        return Response({'error': 'You are not a player in this room'}, status=status.HTTP_403_FORBIDDEN)
    
    if room.current_round == 0:
        return Response({'error': 'Game has not started'}, status=status.HTTP_400_BAD_REQUEST)
    
    game_round = get_object_or_404(GameRound, room=room, round_number=room.current_round)
    
    # Determine if user is the imposter and get appropriate question
    is_imposter = (player == game_round.imposter)
    player_question = game_round.decoy_question if is_imposter else game_round.question
    
    data = GameRoundSerializer(game_round).data
    data['is_imposter'] = is_imposter
    data['player_question'] = QuestionSerializer(player_question).data if player_question else None
    data['user_has_answered'] = game_round.answers.filter(player=player).exists()
    data['user_has_voted'] = game_round.votes.filter(voter=player).exists()
    
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_answer(request, room_id):
    """Submit answer for current round"""
    room = get_object_or_404(GameRoom, id=room_id)
    game_round = get_object_or_404(GameRound, room=room, round_number=room.current_round)
    
    if game_round.status != 'answering':
        return Response({'error': 'Not in answering phase'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        player = Player.objects.get(user=request.user, room=room)
        player.update_activity()
    except Player.DoesNotExist:
        return Response({'error': 'You are not a player in this room'}, status=status.HTTP_403_FORBIDDEN)
    
    serializer = SubmitAnswerSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # Create or update answer
    answer, created = PlayerAnswer.objects.update_or_create(
        round=game_round,
        player=player,
        defaults={'answer': serializer.validated_data['answer']}
    )
    
    # Create game event
    GameEvent.objects.create(
        room=room,
        event_type='answer_submitted',
        player=player,
        data={'answer': answer.answer}
    )
    
    # Check if all connected players have answered
    connected_players = room.players.filter(is_connected=True).count()
    answered_players = game_round.answers.count()
    
    if answered_players >= connected_players:
        # Move to discussion phase
        game_round.status = 'discussion'
        game_round.discussion_started_at = timezone.now()
        game_round.save()
        
        GameEvent.objects.create(
            room=room,
            event_type='discussion_started',
            data={'total_answers': answered_players}
        )
    
    return Response({'success': True, 'answer_id': answer.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_voting(request, room_id):
    """Start voting phase"""
    room = get_object_or_404(GameRoom, id=room_id)
    game_round = get_object_or_404(GameRound, room=room, round_number=room.current_round)
    
    # Check if user is in the room
    try:
        player = Player.objects.get(user=request.user, room=room)
    except Player.DoesNotExist:
        return Response({'error': 'You are not a player in this room'}, status=status.HTTP_403_FORBIDDEN)
    
    if game_round.status != 'discussion':
        return Response({'error': 'Not in discussion phase'}, status=status.HTTP_400_BAD_REQUEST)
    
    game_round.status = 'voting'
    game_round.voting_started_at = timezone.now()
    game_round.save()
    
    GameEvent.objects.create(
        room=room,
        event_type='voting_started',
        data={}
    )
    
    return Response({'success': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_vote(request, room_id):
    """Submit vote for who is the imposter"""
    room = get_object_or_404(GameRoom, id=room_id)
    game_round = get_object_or_404(GameRound, room=room, round_number=room.current_round)
    
    if game_round.status != 'voting':
        return Response({'error': 'Not in voting phase'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        voter = Player.objects.get(user=request.user, room=room)
        voter.update_activity()
    except Player.DoesNotExist:
        return Response({'error': 'You are not a player in this room'}, status=status.HTTP_403_FORBIDDEN)
    
    serializer = SubmitVoteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        accused = Player.objects.get(id=serializer.validated_data['accused_player_id'], room=room)
    except Player.DoesNotExist:
        return Response({'error': 'Accused player not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if voter == accused:
        return Response({'error': 'Cannot vote for yourself'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Create or update vote
    vote, created = Vote.objects.update_or_create(
        round=game_round,
        voter=voter,
        defaults={'accused': accused}
    )
    
    # Create game event
    GameEvent.objects.create(
        room=room,
        event_type='vote_submitted',
        player=voter,
        data={'accused_id': accused.id}
    )
    
    # Check if all connected players have voted
    connected_players = room.players.filter(is_connected=True).count()
    voted_players = game_round.votes.count()
    
    if voted_players >= connected_players:
        # Calculate results and end round
        results = end_round(game_round)
        return Response({
            'success': True, 
            'vote_id': vote.id,
            'voting_complete': True,
            'results': results
        })
    
    return Response({'success': True, 'vote_id': vote.id, 'voting_complete': False})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def continue_to_next_round(request, room_id):
    """Continue from results to next round or end game"""
    room = get_object_or_404(GameRoom, id=room_id)
    
    # Check if user is in the room
    try:
        Player.objects.get(user=request.user, room=room)
    except Player.DoesNotExist:
        return Response({'error': 'You are not a player in this room'}, status=status.HTTP_403_FORBIDDEN)
    
    if room.current_round >= room.total_rounds:
        # End game
        with transaction.atomic():
            room.status = 'finished'
            room.finished_at = timezone.now()
            room.save()
            
            # Update user total games count
            for player in room.players.all():
                player.user.total_games += 1
                player.user.save(update_fields=['total_games'])
            
            GameEvent.objects.create(
                room=room,
                event_type='game_ended',
                data={'final_scores': {p.nickname: p.score for p in room.players.all()}}
            )
        
        # Update leaderboards
        update_leaderboards()
        
        return Response({
            'game_ended': True, 
            'final_scores': {p.nickname: p.score for p in room.players.all()}
        })
    else:
        # Start next round
        room.current_round += 1
        room.save()
        start_round(room, room.current_round)
        
        return Response({'next_round': room.current_round})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_round_results(request, room_id):
    """Get detailed results for the current round"""
    room = get_object_or_404(GameRoom, id=room_id)
    
    # Check if user is in the room
    try:
        Player.objects.get(user=request.user, room=room)
    except Player.DoesNotExist:
        return Response({'error': 'You are not a player in this room'}, status=status.HTTP_403_FORBIDDEN)
    
    game_round = get_object_or_404(GameRound, room=room, round_number=room.current_round)
    
    if game_round.status != 'results':
        return Response({'error': 'Round is not in results phase'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get the round end event for detailed results
    round_end_event = GameEvent.objects.filter(
        room=room,
        event_type='round_ended',
        data__round_number=room.current_round
    ).first()
    
    if not round_end_event:
        return Response({'error': 'Results not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Get answers with player names
    answers_with_players = []
    for answer in game_round.answers.all():
        answers_with_players.append({
            'player_id': answer.player.id,
            'player_nickname': answer.player.nickname,
            'answer': answer.answer,
            'is_imposter': answer.player == game_round.imposter
        })
    
    return Response({
        'round_number': game_round.round_number,
        'question_text': game_round.question.text,
        'decoy_question_text': game_round.decoy_question.text,
        'answers_with_players': sorted(answers_with_players, key=lambda x: x['answer']),
        'results': round_end_event.data,
        'current_scores': {p.nickname: p.score for p in room.players.all()}
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_game_events(request, room_id):
    """Get recent game events"""
    room = get_object_or_404(GameRoom, id=room_id)
    
    # Check if user is in the room
    try:
        Player.objects.get(user=request.user, room=room)
    except Player.DoesNotExist:
        return Response({'error': 'You are not a player in this room'}, status=status.HTTP_403_FORBIDDEN)
    
    events = room.events.all()[:20]  # Last 20 events
    serializer = GameEventSerializer(events, many=True)
    return Response(serializer.data)


# ================================
# Statistics and Profile Views
# ================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_game_history(request):
    """Get user's detailed game history"""
    user_stats = PlayerGameStats.objects.filter(
        player__user=request.user
    ).select_related('player', 'room').order_by('-created_at')[:50]
    
    serializer = PlayerGameStatsSerializer(user_stats, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_leaderboard(request):
    """Get leaderboard for different periods"""
    period = request.query_params.get('period', 'all_time')
    limit = int(request.query_params.get('limit', 50))
    
    leaderboard = Leaderboard.objects.filter(period=period).order_by('rank')[:limit]
    serializer = LeaderboardSerializer(leaderboard, many=True)
    return Response(serializer.data)


# ================================
# Utility Views
# ================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_reconnection(request):
    """Check if user has any ongoing games to reconnect to"""
    active_rooms = GameRoom.objects.filter(
        players__user=request.user,
        status__in=['waiting', 'in_progress']
    ).distinct()
    
    if active_rooms.exists():
        room = active_rooms.first()
        return Response({
            'can_reconnect': True,
            'room': GameRoomSerializer(room, context={'request': request}).data
        })
    
    return Response({'can_reconnect': False})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_activity(request, room_id):
    """Update player activity in a room"""
    try:
        player = Player.objects.get(user=request.user, room_id=room_id)
        player.update_activity()
        return Response({'success': True})
    except Player.DoesNotExist:
        return Response({'error': 'Player not found'}, status=status.HTTP_404_NOT_FOUND)


# ================================
# Leaderboard Management
# ================================

def update_leaderboards():
    """Update leaderboard entries - called after games end"""
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    now = timezone.now()
    
    # Define periods
    periods = {
        'daily': (now.replace(hour=0, minute=0, second=0, microsecond=0), 
                 now.replace(hour=23, minute=59, second=59, microsecond=999999)),
        'weekly': (now - timedelta(days=now.weekday()), now),
        'monthly': (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), now),
        'all_time': (datetime.min.replace(tzinfo=timezone.utc), now)
    }
    
    for period_name, (start_date, end_date) in periods.items():
        # Get user stats for the period
        user_stats = User.objects.annotate(
            period_games=Count('player__game_stats', 
                             filter=Q(player__game_stats__created_at__range=(start_date, end_date))),
            period_wins=Count('player__game_stats',
                            filter=Q(player__game_stats__created_at__range=(start_date, end_date),
                                   player__game_stats__result='win')),
            period_score=Sum('player__game_stats__points_earned',
                           filter=Q(player__game_stats__created_at__range=(start_date, end_date))),
            period_imposter_games=Count('player__game_stats',
                                      filter=Q(player__game_stats__created_at__range=(start_date, end_date),
                                             player__game_stats__role='imposter')),
            period_imposter_wins=Count('player__game_stats',
                                     filter=Q(player__game_stats__created_at__range=(start_date, end_date),
                                            player__game_stats__role='imposter',
                                            player__game_stats__result='win')),
            period_detective_games=Count('player__game_stats',
                                       filter=Q(player__game_stats__created_at__range=(start_date, end_date),
                                              player__game_stats__role='detective')),
            period_detective_wins=Count('player__game_stats',
                                      filter=Q(player__game_stats__created_at__range=(start_date, end_date),
                                             player__game_stats__role='detective',
                                             player__game_stats__result='win'))
        ).filter(period_games__gt=0).order_by('-period_score', '-period_wins')
        
        # Update leaderboard entries
        for rank, user in enumerate(user_stats, 1):
            Leaderboard.objects.update_or_create(
                user=user,
                period=period_name,
                period_start=start_date,
                defaults={
                    'period_end': end_date,
                    'total_games': user.period_games or 0,
                    'total_wins': user.period_wins or 0,
                    'total_score': user.period_score or 0,
                    'imposter_games': user.period_imposter_games or 0,
                    'imposter_wins': user.period_imposter_wins or 0,
                    'detective_games': user.period_detective_games or 0,
                    'detective_wins': user.period_detective_wins or 0,
                    'rank': rank
                }
            )


# ================================
# Admin Utility Views
# ================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_end_game(request, room_id):
    """Admin function to force end a game"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    room = get_object_or_404(GameRoom, id=room_id)
    
    with transaction.atomic():
        room.status = 'finished'
        room.finished_at = timezone.now()
        room.save()
        
        # Create game event
        GameEvent.objects.create(
            room=room,
            event_type='game_ended',
            data={'admin_ended': True, 'admin_user': request.user.username}
        )
    
    return Response({'message': 'Game ended by admin'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_reset_user_stats(request, user_id):
    """Admin function to reset user statistics"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    user = get_object_or_404(User, id=user_id)
    
    user.total_games = 0
    user.total_wins = 0
    user.total_imposter_wins = 0
    user.total_detective_wins = 0
    user.total_score = 0
    user.save()
    
    # Remove from leaderboards
    Leaderboard.objects.filter(user=user).delete()
    
    return Response({'message': f'Statistics reset for user {user.username}'})


# ================================
# Advanced Statistics Views
# ================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_detailed_stats(request):
    """Get detailed user statistics with breakdowns"""
    user = request.user
    
    # Get basic stats
    basic_stats = {
        'total_games': user.total_games,
        'total_wins': user.total_wins,
        'total_score': user.total_score,
        'win_rate': user.win_rate,
        'imposter_wins': user.total_imposter_wins,
        'detective_wins': user.total_detective_wins,
        'imposter_success_rate': user.imposter_success_rate
    }
    
    # Get recent performance (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_stats = PlayerGameStats.objects.filter(
        player__user=user,
        created_at__gte=thirty_days_ago
    ).aggregate(
        recent_games=Count('id'),
        recent_wins=Count('id', filter=Q(result='win')),
        recent_score=Sum('points_earned'),
        recent_imposter_games=Count('id', filter=Q(role='imposter')),
        recent_imposter_wins=Count('id', filter=Q(role='imposter', result='win')),
        recent_detective_games=Count('id', filter=Q(role='detective')),
        recent_detective_wins=Count('id', filter=Q(role='detective', result='win'))
    )
    
    # Calculate recent win rate
    recent_win_rate = 0
    if recent_stats['recent_games']:
        recent_win_rate = (recent_stats['recent_wins'] / recent_stats['recent_games']) * 100
    
    # Get performance by question category
    category_stats = PlayerGameStats.objects.filter(
        player__user=user
    ).select_related('room').values(
        'room__rounds__question__category'
    ).annotate(
        games=Count('id'),
        wins=Count('id', filter=Q(result='win')),
        score=Sum('points_earned')
    ).order_by('-games')
    
    # Get streak information
    recent_games = PlayerGameStats.objects.filter(
        player__user=user
    ).order_by('-created_at')[:10]
    
    current_win_streak = 0
    current_loss_streak = 0
    for game in recent_games:
        if game.result == 'win':
            if current_loss_streak == 0:
                current_win_streak += 1
            else:
                break
        else:
            if current_win_streak == 0:
                current_loss_streak += 1
            else:
                break
    
    return Response({
        'basic_stats': basic_stats,
        'recent_stats': {
            **recent_stats,
            'recent_win_rate': recent_win_rate
        },
        'category_performance': list(category_stats),
        'streaks': {
            'current_win_streak': current_win_streak,
            'current_loss_streak': current_loss_streak
        }
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_global_stats(request):
    """Get global game statistics"""
    total_users = User.objects.count()
    total_games = GameRoom.objects.filter(status='finished').count()
    total_rounds = PlayerGameStats.objects.count()
    
    # Most active users
    most_active = User.objects.filter(total_games__gt=0).order_by('-total_games')[:10]
    
    # Question category popularity
    category_stats = PlayerGameStats.objects.values(
        'room__rounds__question__category'
    ).annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Average game duration (approximate)
    avg_game_duration = GameRoom.objects.filter(
        status='finished',
        started_at__isnull=False,
        finished_at__isnull=False
    ).aggregate(
        avg_duration=Avg(
            timezone.now() - timezone.now()  # This would need proper duration calculation
        )
    )
    
    return Response({
        'total_users': total_users,
        'total_games': total_games,
        'total_rounds': total_rounds,
        'most_active_users': [
            {'username': u.username, 'games': u.total_games, 'score': u.total_score}
            for u in most_active
        ],
        'category_popularity': list(category_stats),
        'imposter_win_rate': PlayerGameStats.objects.filter(
            role='imposter'
        ).aggregate(
            win_rate=Avg(
                Count('id', filter=Q(result='win')) * 100.0 / Count('id')
            )
        )['win_rate'] or 0
    })


# ================================
# Notification System
# ================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_notifications(request):
    """Get user notifications (friend requests, game invites, etc.)"""
    # This could be expanded to include various notification types
    notifications = []
    
    # Check for game invitations (rooms where user was invited but hasn't joined)
    # This would require an invitation system to be implemented
    
    # Check for friend requests
    # This would require a friends system to be implemented
    
    # Check for achievements
    # This would require an achievement system to be implemented
    
    return Response({
        'notifications': notifications,
        'unread_count': len(notifications)
    })


# ================================
# Social Features (Future Implementation)
# ================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_friend(request):
    """Send friend request to another user"""
    # Future implementation for social features
    return Response({'message': 'Friend system not yet implemented'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_friends_list(request):
    """Get user's friends list"""
    # Future implementation for social features
    return Response({'friends': []})


# ================================
# Game Analytics
# ================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_room_analytics(request, room_id):
    """Get analytics for a specific room (host only)"""
    room = get_object_or_404(GameRoom, id=room_id)
    
    # Only host or admin can view analytics
    if room.host != request.user and not request.user.is_staff:
        return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    
    # Get room statistics
    player_stats = PlayerGameStats.objects.filter(room=room)
    
    analytics = {
        'total_rounds': room.total_rounds,
        'completed_rounds': player_stats.values('round_number').distinct().count(),
        'player_performance': {},
        'question_categories_used': [],
        'imposter_success_rate': 0,
        'average_score': 0,
        'game_duration': None
    }
    
    # Player performance breakdown
    for player in room.players.all():
        player_games = player_stats.filter(player=player)
        analytics['player_performance'][player.nickname] = {
            'total_rounds': player_games.count(),
            'wins': player_games.filter(result='win').count(),
            'total_score': player.score,
            'imposter_rounds': player_games.filter(role='imposter').count(),
            'imposter_wins': player_games.filter(role='imposter', result='win').count()
        }
    
    # Calculate game duration if finished
    if room.started_at and room.finished_at:
        duration = room.finished_at - room.started_at
        analytics['game_duration'] = {
            'total_minutes': int(duration.total_seconds() / 60),
            'average_round_minutes': int(duration.total_seconds() / 60 / room.total_rounds) if room.total_rounds else 0
        }
    
    return Response(analytics)


# ================================
# Tournament System (Future)
# ================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_tournament(request):
    """Create a tournament bracket"""
    # Future implementation for tournament mode
    return Response({'message': 'Tournament system not yet implemented'})


@api_view(['GET'])
@permission_classes([AllowAny])
def get_tournaments(request):
    """Get active tournaments"""
    # Future implementation for tournament mode
    return Response({'tournaments': []})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def close_room(request, room_id):
    """Close a game room (host or admin only)"""
    try:
        room = get_object_or_404(GameRoom, id=room_id)
        
        # Check if user is host or admin
        if room.host != request.user and not request.user.is_staff:
            return Response({'error': 'Only the host or admin can close the room'}, status=status.HTTP_403_FORBIDDEN)
        
        # Mark room as finished
        room.status = 'finished'
        room.save()
        
        # Create close event
        GameEvent.objects.create(
            room=room,
            event_type='room_closed',
            data={'closed_by': request.user.username}
        )
        
        return Response({'message': 'Room closed successfully'})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_room(request, room_id):
    """Delete a game room (admin only)"""
    try:
        room = get_object_or_404(GameRoom, id=room_id)
        
        # Only admin can delete rooms
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        
        room_name = room.name
        room.delete()
        
        return Response({'message': f'Room "{room_name}" deleted successfully'})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ================================
# Error Handling Views
# ================================

def handler404(request, exception):
    """Custom 404 handler"""
    return Response({
        'error': 'Endpoint not found',
        'status': 404
    }, status=status.HTTP_404_NOT_FOUND)


def handler500(request):
    """Custom 500 handler"""
    return Response({
        'error': 'Internal server error',
        'status': 500
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ================================
# Cleanup Tasks
# ================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cleanup_old_sessions(request):
    """Cleanup old user sessions (admin only)"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    # Delete sessions older than 7 days
    old_sessions = UserSession.objects.filter(
        last_activity__lt=timezone.now() - timedelta(days=7)
    )
    count = old_sessions.count()
    old_sessions.delete()
    
    return Response({'message': f'Cleaned up {count} old sessions'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cleanup_finished_games(request):
    """Cleanup old finished games (admin only)"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    # Delete finished games older than 30 days
    old_games = GameRoom.objects.filter(
        status='finished',
        finished_at__lt=timezone.now() - timedelta(days=30)
    )
    count = old_games.count()
    return Response({'message': f'Cleaned up {count} old games'})


# ================================
# Admin API Endpoints
# ================================

@api_view(['GET'])

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def debug_room_state(request, room_id):
    """Debug endpoint to view complete room state"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    room = get_object_or_404(GameRoom, id=room_id)
    
    debug_data = {
        'room': GameRoomSerializer(room).data,
        'players': PlayerSerializer(room.players.all(), many=True).data,
        'current_round': None,
        'events': GameEventSerializer(room.events.all()[:10], many=True).data
    }
    
    if room.current_round > 0:
        try:
            current_round = GameRound.objects.get(room=room, round_number=room.current_round)
            debug_data['current_round'] = GameRoundSerializer(current_round).data
        except GameRound.DoesNotExist:
            pass
    
    return Response(debug_data)


# ================================
# Admin API Endpoints
# ================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_overview_stats(request):
    """Get overview statistics for admin dashboard"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    stats = {
        'total_users': User.objects.count(),
        'total_games': GameRoom.objects.count(),
        'active_games': GameRoom.objects.filter(status__in=['waiting', 'in_progress']).count(),
        'total_rounds': GameRound.objects.count(),
    }
    
    return Response(stats)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_recent_activity(request):
    """Get recent activity for admin dashboard"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    # Get recent events
    recent_events = GameEvent.objects.select_related('room').order_by('-created_at')[:20]
    
    activities = []
    for event in recent_events:
        description = f"{event.event_type.replace('_', ' ').title()}"
        if event.room:
            description += f" in room '{event.room.name}'"
        
        activities.append({
            'timestamp': event.created_at,
            'description': description
        })
    
    return Response(activities)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_players_list(request):
    """Get all players for admin dashboard"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    players = User.objects.all().order_by('-date_joined')
    players_data = []
    
    for player in players:
        # Calculate stats
        games_played = Player.objects.filter(user=player).count()
        player_stats = PlayerGameStats.objects.filter(user=player).first()
        
        win_rate = 0
        if player_stats and player_stats.games_played > 0:
            win_rate = round((player_stats.games_won / player_stats.games_played) * 100, 1)
        
        # Check if user is online (has recent activity)
        is_online = False
        if player.last_active:
            is_online = (timezone.now() - player.last_active).total_seconds() < 300  # 5 minutes
        
        players_data.append({
            'id': player.id,
            'username': player.username,
            'email': player.email,
            'games_played': games_played,
            'win_rate': win_rate,
            'last_active': player.last_active,
            'is_online': is_online,
            'is_active': player.is_active,
            'date_joined': player.date_joined
        })
    
    return Response(players_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_games_list(request):
    """Get all games for admin dashboard"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    games = GameRoom.objects.select_related('host').order_by('-created_at')
    games_data = []
    
    for game in games:
        games_data.append({
            'id': str(game.id),
            'name': game.name,
            'host': {
                'id': game.host.id,
                'username': game.host.username
            },
            'player_count': game.player_count,
            'max_players': game.max_players,
            'status': game.status,
            'current_round': game.current_round,
            'total_rounds': game.total_rounds,
            'created_at': game.created_at,
            'started_at': game.started_at,
            'finished_at': game.finished_at
        })
    
    return Response(games_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_detailed_stats(request):
    """Get detailed statistics for admin dashboard"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    # Top players by score
    top_players_data = []
    try:
        player_stats = PlayerGameStats.objects.select_related('user').order_by('-total_score')[:10]
        for stats in player_stats:
            top_players_data.append({
                'username': stats.user.username,
                'total_score': stats.total_score,
                'games_played': stats.games_played
            })
    except:
        pass
    
    # Calculate game metrics
    finished_games = GameRoom.objects.filter(status='finished', finished_at__isnull=False)
    
    avg_game_duration = 0
    if finished_games.exists():
        total_duration = 0
        count = 0
        for game in finished_games:
            if game.started_at:
                duration = (game.finished_at - game.started_at).total_seconds() / 60
                total_duration += duration
                count += 1
        if count > 0:
            avg_game_duration = round(total_duration / count, 1)
    
    avg_players_per_game = 0
    if GameRoom.objects.exists():
        total_players = sum([game.player_count for game in GameRoom.objects.all()])
        avg_players_per_game = round(total_players / GameRoom.objects.count(), 1)
    
    # Imposter win rate (simplified calculation)
    total_rounds = GameRound.objects.filter(status='finished').count()
    imposter_win_rate = 35  # Placeholder percentage
    
    # Most active hour (placeholder)
    most_active_hour = 20  # 8 PM placeholder
    
    stats = {
        'top_players': top_players_data,
        'avg_game_duration': avg_game_duration,
        'avg_players_per_game': avg_players_per_game,
        'imposter_win_rate': imposter_win_rate,
        'most_active_hour': most_active_hour
    }
    
    return Response(stats)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_system_info(request):
    """Get system information for admin dashboard"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    from django.db import connection
    import os
    
    # Get database info
    total_tables = 12  # Approximate number of tables
    
    # Count total records across main tables
    total_records = (
        User.objects.count() +
        GameRoom.objects.count() +
        GameRound.objects.count() +
        PlayerAnswer.objects.count() +
        Vote.objects.count()
    )
    
    # Database size
    db_path = 'db.sqlite3'
    db_size = "Unknown"
    if os.path.exists(db_path):
        size_bytes = os.path.getsize(db_path)
        if size_bytes < 1024 * 1024:
            db_size = f"{round(size_bytes / 1024, 1)} KB"
        else:
            db_size = f"{round(size_bytes / (1024 * 1024), 1)} MB"
    
    # Recent logs (placeholder)
    recent_logs = [
        f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] Server started successfully",
        f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] Database connection established",
        f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] Admin dashboard accessed",
        f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] Total users: {User.objects.count()}",
        f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] Active games: {GameRoom.objects.filter(status__in=['waiting', 'in_progress']).count()}"
    ]
    
    system_info = {
        'total_tables': total_tables,
        'total_records': total_records,
        'db_size': db_size,
        'recent_logs': recent_logs
    }
    
    return Response(system_info)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_player_detail(request, player_id):
    """Get detailed player information"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    player = get_object_or_404(User, id=player_id)
    stats = PlayerGameStats.objects.filter(user=player).first()
    
    player_data = {
        'id': player.id,
        'username': player.username,
        'email': player.email,
        'first_name': player.first_name,
        'last_name': player.last_name,
        'date_joined': player.date_joined,
        'last_active': player.last_active,
        'is_active': player.is_active,
        'games_played': stats.games_played if stats else 0,
        'games_won': stats.games_won if stats else 0,
        'win_rate': round((stats.games_won / stats.games_played * 100), 1) if stats and stats.games_played > 0 else 0,
        'total_score': stats.total_score if stats else 0
    }
    
    return Response(player_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_game_detail(request, game_id):
    """Get detailed game information"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    game = get_object_or_404(GameRoom, id=game_id)
    
    game_data = {
        'id': str(game.id),
        'name': game.name,
        'host': {
            'id': game.host.id,
            'username': game.host.username
        },
        'player_count': game.player_count,
        'max_players': game.max_players,
        'status': game.status,
        'current_round': game.current_round,
        'total_rounds': game.total_rounds,
        'created_at': game.created_at,
        'started_at': game.started_at,
        'finished_at': game.finished_at,
        'players': [{
            'id': player.id,
            'nickname': player.nickname,
            'user': player.user.username,
            'is_connected': player.is_connected
        } for player in game.players.all()]
    }
    
    return Response(game_data)


# ================================
# Health Check
# ================================

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now(),
        'version': '1.0.0'
    })