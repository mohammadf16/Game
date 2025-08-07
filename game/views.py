from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.utils import timezone
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
import random

from .models import (
    Question, DecoyQuestion, GameRoom, Player, 
    GameRound, PlayerAnswer, Vote, GameEvent
)
from .serializers import (
    GameRoomSerializer, GameRoomCreateSerializer, PlayerSerializer,
    GameRoundSerializer, JoinRoomSerializer, SubmitAnswerSerializer,
    SubmitVoteSerializer, QuestionSerializer, GameEventSerializer
)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_user(request):
    """Create a new user for the game"""
    username = request.data.get('username')
    if not username:
        return Response({'error': 'Username is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Create user if doesn't exist
    user, created = User.objects.get_or_create(
        username=username,
        defaults={'first_name': username}
    )
    
    # Auto login
    login(request, user)
    
    return Response({
        'user_id': user.id,
        'username': user.username,
        'created': created
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def list_rooms(request):
    """List all available game rooms"""
    rooms = GameRoom.objects.filter(status__in=['waiting', 'in_progress']).order_by('-created_at')
    serializer = GameRoomSerializer(rooms, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_room(request):
    """Create a new game room"""
    # Get or create user
    username = request.data.get('username')
    if not username:
        return Response({'error': 'Username is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={'first_name': username}
    )
    
    serializer = GameRoomCreateSerializer(data=request.data)
    if serializer.is_valid():
        room = serializer.save(host=user)
        
        # Automatically add host as a player
        Player.objects.create(
            user=user,
            room=room,
            nickname=username  # Use username as nickname for host
        )
        
        # Create game event
        GameEvent.objects.create(
            room=room,
            event_type='player_joined',
            data={'host': username, 'nickname': username}
        )
        
        return Response(GameRoomSerializer(room).data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_room(request, room_id):
    """Get room details"""
    room = get_object_or_404(GameRoom, id=room_id)
    serializer = GameRoomSerializer(room)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny])
def join_room(request, room_id):
    """Join a game room"""
    room = get_object_or_404(GameRoom, id=room_id)
    
    if room.status != 'waiting':
        return Response({'error': 'Room is not accepting new players'}, status=status.HTTP_400_BAD_REQUEST)
    
    if room.player_count >= room.max_players:
        return Response({'error': 'Room is full'}, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = JoinRoomSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    username = request.data.get('username')
    nickname = serializer.validated_data['nickname']
    
    # Get or create user
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={'first_name': username}
    )
    
    # Check if player already in room
    if Player.objects.filter(user=user, room=room).exists():
        return Response({'error': 'You are already in this room'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Create player
    player = Player.objects.create(
        user=user,
        room=room,
        nickname=nickname
    )
    
    # Create game event
    GameEvent.objects.create(
        room=room,
        event_type='player_joined',
        player=player,
        data={'nickname': nickname}
    )
    
    return Response(PlayerSerializer(player).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def start_game(request, room_id):
    """Start the game"""
    room = get_object_or_404(GameRoom, id=room_id)
    
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
    
    return Response(GameRoomSerializer(room).data)


def start_round(room, round_number):
    """Start a new round"""
    # Get random question and decoy question
    question = Question.objects.filter(is_active=True).order_by('?').first()
    decoy_question = DecoyQuestion.objects.filter(is_active=True).order_by('?').first()
    
    if not question or not decoy_question:
        raise ValueError("No questions available")
    
    # Select random imposter
    players = list(room.players.filter(is_connected=True))
    imposter = random.choice(players)
    
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


@api_view(['GET'])
@permission_classes([AllowAny])
def get_current_round(request, room_id):
    """Get current round information"""
    room = get_object_or_404(GameRoom, id=room_id)
    
    if room.current_round == 0:
        return Response({'error': 'Game has not started'}, status=status.HTTP_400_BAD_REQUEST)
    
    game_round = get_object_or_404(GameRound, room=room, round_number=room.current_round)
    
    # Get player info to determine if they're the imposter
    username = request.query_params.get('username')
    is_imposter = False
    player_question = None
    
    if username:
        try:
            user = User.objects.get(username=username)
            player = Player.objects.get(user=user, room=room)
            is_imposter = (player == game_round.imposter)
            player_question = game_round.decoy_question if is_imposter else game_round.question
        except (User.DoesNotExist, Player.DoesNotExist):
            pass
    
    data = GameRoundSerializer(game_round).data
    data['is_imposter'] = is_imposter
    data['player_question'] = QuestionSerializer(player_question).data if player_question else None
    
    return Response(data)


@api_view(['POST'])
@permission_classes([AllowAny])
def submit_answer(request, room_id):
    """Submit answer for current round"""
    room = get_object_or_404(GameRoom, id=room_id)
    game_round = get_object_or_404(GameRound, room=room, round_number=room.current_round)
    
    if game_round.status != 'answering':
        return Response({'error': 'Not in answering phase'}, status=status.HTTP_400_BAD_REQUEST)
    
    username = request.data.get('username')
    if not username:
        return Response({'error': 'Username is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(username=username)
        player = Player.objects.get(user=user, room=room)
    except (User.DoesNotExist, Player.DoesNotExist):
        return Response({'error': 'Player not found'}, status=status.HTTP_404_NOT_FOUND)
    
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
    
    # Check if all players have answered
    total_players = room.players.filter(is_connected=True).count()
    answered_players = game_round.answers.count()
    
    if answered_players >= total_players:
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
@permission_classes([AllowAny])
def start_voting(request, room_id):
    """Start voting phase"""
    room = get_object_or_404(GameRoom, id=room_id)
    game_round = get_object_or_404(GameRound, room=room, round_number=room.current_round)
    
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
@permission_classes([AllowAny])
def submit_vote(request, room_id):
    """Submit vote for who is the imposter"""
    room = get_object_or_404(GameRoom, id=room_id)
    game_round = get_object_or_404(GameRound, room=room, round_number=room.current_round)
    
    if game_round.status != 'voting':
        return Response({'error': 'Not in voting phase'}, status=status.HTTP_400_BAD_REQUEST)
    
    username = request.data.get('username')
    if not username:
        return Response({'error': 'Username is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(username=username)
        voter = Player.objects.get(user=user, room=room)
    except (User.DoesNotExist, Player.DoesNotExist):
        return Response({'error': 'Player not found'}, status=status.HTTP_404_NOT_FOUND)
    
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
    
    # Check if all players have voted
    total_players = room.players.filter(is_connected=True).count()
    voted_players = game_round.votes.count()
    
    if voted_players >= total_players:
        # Calculate results and end round
        results = end_round(game_round)
        return Response({
            'success': True, 
            'vote_id': vote.id,
            'voting_complete': True,
            'results': results
        })
    
    return Response({'success': True, 'vote_id': vote.id, 'voting_complete': False})


def end_round(game_round):
    """End the current round and calculate results"""
    room = game_round.room
    
    # Calculate vote results
    vote_counts = {}
    voter_choices = {}  # Track who voted for whom
    
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
        
        # Advanced scoring system
        for player in room.players.filter(is_connected=True):
            if player == game_round.imposter:
                # Imposter scoring
                if not imposter_caught:
                    player.score += 3  # Bonus for successful deception
                # No penalty for being caught
            else:
                # Detective scoring
                player_vote = game_round.votes.filter(voter=player).first()
                if player_vote:
                    if imposter_caught and player_vote.accused == game_round.imposter:
                        # Correctly voted for imposter
                        player.score += 2
                    elif not imposter_caught and player_vote.accused != game_round.imposter:
                        # Correctly didn't vote for imposter (but imposter won)
                        player.score += 1
                    # No points for incorrect votes
            player.save()
    
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
    
    # Wait 10 seconds in results phase, then continue
    # This will be handled by frontend polling
    
    return {
        'imposter_caught': imposter_caught,
        'imposter': game_round.imposter,
        'most_voted_player': most_voted_player,
        'vote_counts': vote_counts,
        'voter_choices': voter_choices
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def continue_to_next_round(request, room_id):
    """Continue from results to next round or end game"""
    room = get_object_or_404(GameRoom, id=room_id)
    
    if room.current_round >= room.total_rounds:
        # End game
        room.status = 'finished'
        room.finished_at = timezone.now()
        room.save()
        
        GameEvent.objects.create(
            room=room,
            event_type='game_ended',
            data={'final_scores': {p.nickname: p.score for p in room.players.all()}}
        )
        
        return Response({'game_ended': True, 'final_scores': {p.nickname: p.score for p in room.players.all()}})
    else:
        # Start next round
        room.current_round += 1
        room.save()
        start_round(room, room.current_round)
        
        return Response({'next_round': room.current_round})


@api_view(['GET'])
@permission_classes([AllowAny])
def get_round_results(request, room_id):
    """Get detailed results for the current round"""
    room = get_object_or_404(GameRoom, id=room_id)
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
@permission_classes([AllowAny])
def get_game_events(request, room_id):
    """Get recent game events"""
    room = get_object_or_404(GameRoom, id=room_id)
    events = room.events.all()[:20]  # Last 20 events
    serializer = GameEventSerializer(events, many=True)
    return Response(serializer.data)
