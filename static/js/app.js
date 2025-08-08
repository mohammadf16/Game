// Number Hunt Game JavaScript
class NumberHuntGame {
    constructor() {
        this.currentUser = null;
        this.currentRoom = null;
        this.currentRound = null;
        this.gameState = 'menu'; // menu, lobby, playing, finished
        this.pollInterval = null;
        
        this.initializeApp();
    }
    
    initializeApp() {
        this.showMenu();
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // Menu buttons
        document.getElementById('createRoomBtn')?.addEventListener('click', () => this.showCreateRoom());
        document.getElementById('joinRoomBtn')?.addEventListener('click', () => this.showJoinRoom());
        
        // Form submissions
        document.getElementById('createRoomForm')?.addEventListener('submit', (e) => this.handleCreateRoom(e));
        document.getElementById('joinRoomForm')?.addEventListener('submit', (e) => this.handleJoinRoom(e));
        document.getElementById('answerForm')?.addEventListener('submit', (e) => this.handleSubmitAnswer(e));
        
        // Game actions
        document.getElementById('startGameBtn')?.addEventListener('click', () => this.startGame());
        document.getElementById('startVotingBtn')?.addEventListener('click', () => this.startVoting());
        document.getElementById('submitVoteBtn')?.addEventListener('click', () => this.submitVote());
        document.getElementById('continueBtn')?.addEventListener('click', () => this.continueToNextRound());
        
        // Back buttons
        document.querySelectorAll('.back-btn').forEach(btn => {
            btn.addEventListener('click', () => this.showMenu());
        });
    }
    
    // API Methods
    async apiCall(endpoint, method = 'GET', data = null) {
        const url = endpoint;
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            }
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        try {
            const response = await fetch(url, options);
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.error || 'API call failed');
            }
            
            return result;
        } catch (error) {
            this.showNotification(error.message, 'error');
            throw error;
        }
    }
    
    // UI Management
    showScreen(screenId) {
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.add('hidden');
        });
        document.getElementById(screenId)?.classList.remove('hidden');
    }
    
    showMenu() {
        this.gameState = 'menu';
        this.showScreen('menuScreen');
        this.stopPolling();
    }
    
    showCreateRoom() {
        this.showScreen('createRoomScreen');
    }
    
    showJoinRoom() {
        this.showScreen('joinRoomScreen');
        this.loadAvailableRooms();
    }
    
    showLobby() {
        this.gameState = 'lobby';
        this.showScreen('lobbyScreen');
        this.startPolling();
    }
    
    showGame() {
        this.gameState = 'playing';
        this.showScreen('gameScreen');
        this.startPolling();
    }
    
    // Room Management
    async handleCreateRoom(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        
        try {
            const roomData = {
                username: formData.get('username'),
                name: formData.get('roomName'),
                max_players: parseInt(formData.get('maxPlayers')),
                total_rounds: parseInt(formData.get('totalRounds'))
            };
            
            this.currentRoom = await this.apiCall('/api/rooms/create/', 'POST', roomData);
            this.currentUser = roomData.username;
            
            this.showNotification('Room created successfully!', 'success');
            this.showLobby();
            this.updateLobbyUI();
            
        } catch (error) {
            console.error('Failed to create room:', error);
        }
    }
    
    async handleJoinRoom(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const roomId = formData.get('roomId');
        
        try {
            const joinData = {
                username: formData.get('username'),
                nickname: formData.get('nickname')
            };
            
            await this.apiCall(`/api/rooms/${roomId}/join/`, 'POST', joinData);
            this.currentRoom = await this.apiCall(`/api/rooms/${roomId}/`);
            this.currentUser = joinData.username;
            
            this.showNotification('Joined room successfully!', 'success');
            this.showLobby();
            this.updateLobbyUI();
            
        } catch (error) {
            console.error('Failed to join room:', error);
        }
    }
    
    async loadAvailableRooms() {
        try {
            const rooms = await this.apiCall('/api/rooms/');
            this.displayAvailableRooms(rooms);
        } catch (error) {
            console.error('Failed to load rooms:', error);
        }
    }
    
    displayAvailableRooms(rooms) {
        const container = document.getElementById('availableRooms');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (rooms.length === 0) {
            container.innerHTML = '<p class="text-center">No rooms available. Create one!</p>';
            return;
        }
        
        rooms.forEach(room => {
            const roomCard = document.createElement('div');
            roomCard.className = 'card';
            roomCard.innerHTML = `
                <div class="card-header">
                    <h3 class="card-title">${room.name}</h3>
                    <span class="badge ${room.status === 'waiting' ? 'success' : 'warning'}">${room.status}</span>
                </div>
                <div class="room-info">
                    <p>Players: ${room.player_count}/${room.max_players}</p>
                    <p>Rounds: ${room.total_rounds}</p>
                    <p>Host: ${room.host.username}</p>
                </div>
                <div class="room-actions">
                    <button class="btn btn-primary" onclick="game.selectRoom('${room.id}')" 
                            ${room.status !== 'waiting' || room.player_count >= room.max_players ? 'disabled' : ''}>
                        ${room.status !== 'waiting' ? 'In Progress' : room.player_count >= room.max_players ? 'Full' : 'Join'}
                    </button>
                </div>
            `;
            container.appendChild(roomCard);
        });
    }
    
    selectRoom(roomId) {
        document.getElementById('selectedRoomId').value = roomId;
    }
    
    // Game Flow
    async startGame() {
        try {
            await this.apiCall(`/api/rooms/${this.currentRoom.id}/start/`, 'POST');
            this.showNotification('Game started!', 'success');
            this.showGame();
        } catch (error) {
            console.error('Failed to start game:', error);
        }
    }
    
    async handleSubmitAnswer(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        
        try {
            const answerData = {
                username: this.currentUser,
                answer: parseInt(formData.get('answer'))
            };
            
            await this.apiCall(`/api/rooms/${this.currentRoom.id}/submit-answer/`, 'POST', answerData);
            this.showNotification('Answer submitted!', 'success');
            
            // Add a small delay before disabling form to prevent quick clearing
            setTimeout(() => {
                // Disable form
                e.target.querySelector('input[type="number"]').disabled = true;
                e.target.querySelector('button').disabled = true;
            }, 1000);
            
        } catch (error) {
            console.error('Failed to submit answer:', error);
        }
    }
    
    async startVoting() {
        try {
            await this.apiCall(`/api/rooms/${this.currentRoom.id}/start-voting/`, 'POST');
            this.showNotification('Voting phase started!', 'success');
        } catch (error) {
            console.error('Failed to start voting:', error);
        }
    }
    
    async submitVote() {
        const selectedPlayer = document.querySelector('input[name="suspectPlayer"]:checked');
        if (!selectedPlayer) {
            this.showNotification('Please select a player to vote for', 'warning');
            return;
        }
        
        try {
            const voteData = {
                username: this.currentUser,
                accused_player_id: parseInt(selectedPlayer.value)
            };
            
            const response = await this.apiCall(`/api/rooms/${this.currentRoom.id}/submit-vote/`, 'POST', voteData);
            if (!response.ok) {
                throw new Error(response.statusText);
            }
            
            const result = await response.json();
            this.showNotification('Vote submitted!', 'success');
            
            // Disable voting
            document.querySelectorAll('input[name="suspectPlayer"]').forEach(input => {
                input.disabled = true;
            });
            document.getElementById('submitVoteBtn').disabled = true;
            
            // If voting is complete, show notification
            if (result.voting_complete) {
                this.showNotification('All votes submitted! Calculating results...', 'success');
            }
            
        } catch (error) {
            console.error('Failed to submit vote:', error);
            // Show a more user-friendly error message
            this.showNotification('Failed to submit vote. Please try again.', 'error');
        }
    }
    
    // Polling for updates
    startPolling() {
        this.stopPolling();
        this.pollInterval = setInterval(() => {
            this.pollForUpdates();
        }, 2000);
    }
    
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }
    
    async pollForUpdates() {
        try {
            if (this.gameState === 'lobby') {
                this.currentRoom = await this.apiCall(`/api/rooms/${this.currentRoom.id}/`);
                this.updateLobbyUI();
                
                if (this.currentRoom.status === 'in_progress') {
                    this.showGame();
                }
            } else if (this.gameState === 'playing') {
                this.currentRoom = await this.apiCall(`/api/rooms/${this.currentRoom.id}/`);
                this.currentRound = await this.apiCall(`/api/rooms/${this.currentRoom.id}/current-round/?username=${this.currentUser}`);
                this.updateGameUI();
                
                if (this.currentRoom.status === 'finished') {
                    this.showResults();
                }
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }
    
    // UI Updates
    updateLobbyUI() {
        if (!this.currentRoom) return;
        
        // Update room info
        document.getElementById('lobbyRoomName').textContent = this.currentRoom.name;
        document.getElementById('lobbyPlayerCount').textContent = `${this.currentRoom.player_count}/${this.currentRoom.max_players}`;
        
        // Update players list
        const playersContainer = document.getElementById('lobbyPlayers');
        playersContainer.innerHTML = '';
        
        this.currentRoom.players.forEach(player => {
            const playerCard = document.createElement('div');
            playerCard.className = `player-card ${player.is_connected ? 'connected' : 'disconnected'}`;
            playerCard.innerHTML = `
                <div class="player-name">${player.nickname}</div>
                <div class="player-score">Score: ${player.score}</div>
                ${player.user.username === this.currentRoom.host.username ? '<div class="host-badge">HOST</div>' : ''}
            `;
            playersContainer.appendChild(playerCard);
        });
        
        // Show/hide start button
        const startBtn = document.getElementById('startGameBtn');
        if (startBtn) {
            startBtn.style.display = (this.currentRoom.host.username === this.currentUser && this.currentRoom.can_start) ? 'block' : 'none';
        }
    }
    
    updateGameUI() {
        if (!this.currentRound) return;
        
        // Update round info
        document.getElementById('currentRoundNumber').textContent = this.currentRoom.current_round;
        document.getElementById('totalRounds').textContent = this.currentRoom.total_rounds;
        
        // Update question
        if (this.currentRound.player_question) {
            document.getElementById('questionText').textContent = this.currentRound.player_question.text;
            document.getElementById('questionCategory').textContent = this.currentRound.player_question.category;
        }
        
        // Update role indicator
        const roleIndicator = document.getElementById('roleIndicator');
        if (roleIndicator) {
            roleIndicator.textContent = this.currentRound.is_imposter ? 'You are the IMPOSTER!' : 'You are a DETECTIVE';
            roleIndicator.className = this.currentRound.is_imposter ? 'role-imposter' : 'role-detective';
        }
        
        // Update phase
        this.updateGamePhase();
        
        // Reset answer form if we're in answering phase
        if (this.currentRound.status === 'answering') {
            const answerForm = document.getElementById('answerForm');
            if (answerForm) {
                // Reset and enable the form inputs
                answerForm.reset();
                const answerInput = answerForm.querySelector('input[type="number"]');
                const submitButton = answerForm.querySelector('button');
                if (answerInput) answerInput.disabled = false;
                if (submitButton) submitButton.disabled = false;
            }
        }
        
        // Update answers if available
        if (this.currentRound.answers && this.currentRound.answers.length > 0) {
            this.displayAnswers();
        }
        
        // Update players for voting
        if (this.currentRound.status === 'voting') {
            this.displayVotingOptions();
        }
    }
    
    updateGamePhase() {
        const phaseTitle = document.getElementById('phaseTitle');
        const phaseDescription = document.getElementById('phaseDescription');
        const answerSection = document.getElementById('answerSection');
        const discussionSection = document.getElementById('discussionSection');
        const votingSection = document.getElementById('votingSection');
        const resultsSection = document.getElementById('resultsSection');
        
        // Hide all sections first
        [answerSection, discussionSection, votingSection, resultsSection].forEach(section => {
            if (section) section.classList.add('hidden');
        });
        
        switch (this.currentRound.status) {
            case 'answering':
                phaseTitle.textContent = 'Answer Phase';
                phaseDescription.textContent = 'Submit your numerical answer to the question';
                answerSection?.classList.remove('hidden');
                break;
                
            case 'discussion':
                phaseTitle.textContent = 'Discussion Phase';
                phaseDescription.textContent = 'Discuss the answers and try to identify the imposter';
                discussionSection?.classList.remove('hidden');
                this.displayRevealedQuestions();
                break;
                
            case 'voting':
                phaseTitle.textContent = 'Voting Phase';
                phaseDescription.textContent = 'Vote for who you think is the imposter';
                votingSection?.classList.remove('hidden');
                break;
                
            case 'results':
                phaseTitle.textContent = 'Round Results';
                phaseDescription.textContent = 'See who was the imposter and how everyone voted';
                resultsSection?.classList.remove('hidden');
                this.loadRoundResults();
                break;
        }
    }
    
    displayRevealedQuestions() {
        // Check if we have revealed questions from game events
        this.fetchAndDisplayRevealedQuestions();
    }
    
    async fetchAndDisplayRevealedQuestions() {
        try {
            const events = await this.apiCall(`/api/rooms/${this.currentRoom.id}/events/`);
            const discussionEvent = events.find(event => event.event_type === 'discussion_started');
            
            if (discussionEvent && discussionEvent.data) {
                const { question_text, decoy_question_text } = discussionEvent.data;
                this.showRevealedQuestions(question_text, decoy_question_text);
            }
        } catch (error) {
            console.error('Failed to fetch revealed questions:', error);
        }
    }
    
    showRevealedQuestions(questionText, decoyQuestionText) {
        const answersContainer = document.getElementById('answersDisplay');
        if (!answersContainer) return;
        
        // Create revealed questions section
        const revealedQuestionsHtml = `
            <div class="revealed-questions mb-3">
                <h4 class="text-center mb-2">📝 Questions Revealed!</h4>
                <div class="questions-reveal">
                    <div class="question-box detective-question">
                        <h5>🕵️ Detective Question (Real Question):</h5>
                        <p>${questionText}</p>
                    </div>
                    <div class="question-box imposter-question">
                        <h5>🎭 Imposter Question (Decoy Question):</h5>
                        <p>${decoyQuestionText}</p>
                    </div>
                </div>
                <div class="reveal-note">
                    <p><strong>💡 Now you know:</strong> The imposter received the decoy question while detectives got the real question!</p>
                </div>
            </div>
        `;
        
        // Add revealed questions before answers
        answersContainer.innerHTML = revealedQuestionsHtml + '<h3>Submitted Answers:</h3>';
        
        // Add answers if available
        if (this.currentRound.answers && this.currentRound.answers.length > 0) {
            const answersGrid = document.createElement('div');
            answersGrid.className = 'answers-with-names';
            
            const sortedAnswers = [...this.currentRound.answers].sort((a, b) => a.answer - b.answer);
            
            sortedAnswers.forEach(answer => {
                const answerCard = document.createElement('div');
                answerCard.className = 'answer-card-discussion';
                answerCard.innerHTML = `
                    <div class="answer-number-large">${answer.answer}</div>
                    <div class="answer-player-name">${answer.player.nickname}</div>
                `;
                answersGrid.appendChild(answerCard);
            });
            
            answersContainer.appendChild(answersGrid);
        }
    }

    displayAnswers() {
        const answersContainer = document.getElementById('answersDisplay');
        if (!answersContainer || !this.currentRound.answers) return;
        
        answersContainer.innerHTML = '<h3>Submitted Answers:</h3>';
        const answersGrid = document.createElement('div');
        answersGrid.className = 'answers-with-names';
        
        // Sort answers for display
        const sortedAnswers = [...this.currentRound.answers].sort((a, b) => a.answer - b.answer);
        
        sortedAnswers.forEach(answer => {
            const answerCard = document.createElement('div');
            answerCard.className = 'answer-card-discussion';
            answerCard.innerHTML = `
                <div class="answer-number-large">${answer.answer}</div>
                <div class="answer-player-name">${answer.player.nickname}</div>
            `;
            answersGrid.appendChild(answerCard);
        });
        
        answersContainer.appendChild(answersGrid);
    }
    
    displayVotingOptions() {
        const votingContainer = document.getElementById('votingOptions');
        if (!votingContainer || !this.currentRoom.players) return;
        
        votingContainer.innerHTML = '';
        
        this.currentRoom.players.forEach(player => {
            // Don't show current user as voting option
            if (player.user.username === this.currentUser) return;
            
            const voteOption = document.createElement('label');
            voteOption.className = 'vote-option';
            voteOption.innerHTML = `
                <input type="radio" name="suspectPlayer" value="${player.id}" style="display: none;">
                <div class="player-name">${player.nickname}</div>
                <div class="player-score">Score: ${player.score}</div>
            `;
            
            voteOption.addEventListener('click', () => {
                document.querySelectorAll('.vote-option').forEach(opt => opt.classList.remove('selected'));
                voteOption.classList.add('selected');
                voteOption.querySelector('input').checked = true;
            });
            
            votingContainer.appendChild(voteOption);
        });
        
        // Ensure submit vote button is enabled when displaying voting options
        const submitVoteBtn = document.getElementById('submitVoteBtn');
        if (submitVoteBtn) {
            submitVoteBtn.disabled = false;
        }
    }
    
    async loadRoundResults() {
        try {
            const results = await this.apiCall(`/api/rooms/${this.currentRoom.id}/results/`);
            this.displayRoundResults(results);
        } catch (error) {
            console.error('Failed to load round results:', error);
        }
    }
    
    displayRoundResults(results) {
        const resultsContainer = document.getElementById('roundResultsContent');
        if (!resultsContainer) return;
        
        const { answers_with_players, results: roundResults, current_scores } = results;
        
        resultsContainer.innerHTML = `
            <div class="results-header">
                <h3>🎭 The Imposter was: <span class="imposter-name">${roundResults.imposter_nickname}</span></h3>
                <div class="result-status ${roundResults.imposter_caught ? 'detectives-win' : 'imposter-win'}">
                    ${roundResults.imposter_caught ? '🕵️ Detectives Win!' : '🎭 Imposter Wins!'}
                </div>
            </div>
            
            <div class="questions-reveal">
                <div class="question-box detective-question">
                    <h4>🕵️ Detective Question (Real Question):</h4>
                    <p>${results.question_text}</p>
                </div>
                <div class="question-box imposter-question">
                    <h4>🎭 Imposter Question (Decoy Question):</h4>
                    <p>${results.decoy_question_text}</p>
                </div>
            </div>
            
            <div class="imposter-reveal-note">
                <p><strong>📝 Note:</strong> The imposter received the decoy question while detectives got the real question!</p>
            </div>
            
            <div class="answers-reveal">
                <h4>📊 Who Answered What:</h4>
                <div class="answers-with-players">
                    ${answers_with_players.map(answer => `
                        <div class="answer-reveal ${answer.is_imposter ? 'imposter-answer' : 'detective-answer'}">
                            <div class="answer-number">${answer.answer}</div>
                            <div class="answer-player">
                                ${answer.player_nickname}
                                ${answer.is_imposter ? '🎭' : '🕵️'}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            <div class="voting-results">
                <h4>🗳️ Voting Results:</h4>
                <div class="vote-breakdown">
                    ${Object.entries(roundResults.vote_counts || {}).map(([playerId, votes]) => {
                        const player = this.currentRoom.players.find(p => p.id == playerId);
                        return `
                            <div class="vote-result">
                                <span class="voted-player">${player ? player.nickname : 'Unknown'}</span>
                                <span class="vote-count">${votes} vote${votes !== 1 ? 's' : ''}</span>
                            </div>
                        `;
                    }).join('')}
                </div>
                
                <div class="individual-votes">
                    <h5>Individual Votes:</h5>
                    ${Object.values(roundResults.voter_choices || {}).map(vote => `
                        <div class="individual-vote">
                            <span class="voter">${vote.voter_nickname}</span> voted for 
                            <span class="accused">${vote.accused_nickname}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            <div class="current-scores">
                <h4>🏆 Current Scores:</h4>
                <div class="scores-grid">
                    ${Object.entries(current_scores).map(([nickname, score]) => `
                        <div class="score-item">
                            <span class="player-name">${nickname}</span>
                            <span class="player-score">${score} points</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    async continueToNextRound() {
        try {
            const result = await this.apiCall(`/api/rooms/${this.currentRoom.id}/continue/`, 'POST');
            
            if (result.game_ended) {
                this.showFinalResults(result.final_scores);
            } else {
                this.showNotification(`Starting Round ${result.next_round}!`, 'success');
                // The polling will handle the UI update
            }
        } catch (error) {
            console.error('Failed to continue to next round:', error);
        }
    }
    
    showResults() {
        // Implementation for showing final results
        this.gameState = 'finished';
        this.stopPolling();
        this.showNotification('Game finished!', 'success');
    }
    
    // Utility Methods
    showNotification(message, type = 'success') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.classList.add('show');
        }, 100);
        
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }
}

// Initialize the game when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.game = new NumberHuntGame();
});
