document.addEventListener('DOMContentLoaded', function() {
    // Определение активной страницы в навигации
    function setActiveNavLink() {
        const currentPath = window.location.pathname;
        const navLinks = document.querySelectorAll('.nav-link');
        
        navLinks.forEach(link => {
            link.classList.remove('active');
            const linkPath = new URL(link.href).pathname;
            if (linkPath === currentPath || (currentPath === '/' && linkPath === '/')) {
                link.classList.add('active');
            }
        });
    }
    
    setActiveNavLink();
    
    const btnAnalyze = document.getElementById('btn-analyze');

    // Выполняем код только если мы на главной странице (где есть кнопка 'btn-analyze')
    if (btnAnalyze) {
        const btnStartDownload = document.getElementById('btn-start-download');
        const hdrezkaUrlInput = document.getElementById('hdrezka-url');
        const proxyInput = document.getElementById('proxy');
        const analyzeStatus = document.getElementById('analyze-status');
        
        const step2 = document.getElementById('step-2');
        const seriesParams = document.getElementById('series-params');
        const movieParams = document.getElementById('movie-params');
        
        const seasonSelect = document.getElementById('season');
        const episodeSelect = document.getElementById('episode');
        const translatorSelect = document.getElementById('translator');
        const qualitySelect = document.getElementById('quality');
        
        const translatorMovieSelect = document.getElementById('translator-movie');
        const qualityMovieSelect = document.getElementById('quality-movie');

        let analysisData = {};

        btnAnalyze.addEventListener('click', () => {
            const url = hdrezkaUrlInput.value;
            const proxy = proxyInput.value;

            if (!url) {
                analyzeStatus.textContent = 'Пожалуйста, введите URL.';
                analyzeStatus.className = 'status-message error';
                return;
            }

            analyzeStatus.textContent = 'Анализ...';
            analyzeStatus.className = 'status-message info';
            btnAnalyze.disabled = true;

            fetch('/api/workflow/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url, proxy }),
            })
            .then(response => response.json())
            .then(data => {
                btnAnalyze.disabled = false;
                if (data.success) {
                    analysisData = data;
                    analyzeStatus.textContent = 'Анализ завершен.';
                    analyzeStatus.className = 'status-message success';
                    populateStep2(data);
                    step2.style.display = 'block';
                } else {
                    analyzeStatus.textContent = `Ошибка: ${data.error}`;
                    analyzeStatus.className = 'status-message error';
                }
            })
            .catch(error => {
                btnAnalyze.disabled = false;
                analyzeStatus.textContent = `Ошибка сети: ${error}`;
                analyzeStatus.className = 'status-message error';
            });
        });

        function populateStep2(data) {
            // Очищаем селекты
            seasonSelect.innerHTML = '';
            episodeSelect.innerHTML = '';
            translatorSelect.innerHTML = '';
            translatorMovieSelect.innerHTML = '';

            // Заполняем озвучки
            if (data.translators) {
                for (const translatorId in data.translators) {
                    const option = new Option(data.translators[translatorId].name, translatorId);
                    translatorSelect.add(option.cloneNode(true));
                    translatorMovieSelect.add(option);
                }
            }

            if (data.type === 'tv_series' || data.type === 'TVSeries' || (data.series_info && Object.keys(data.series_info).length > 0)) {
                seriesParams.style.display = 'block';
                movieParams.style.display = 'none';

                // Заполняем сезоны
                if (data.series_info) {
                    for (const seasonNum in data.series_info) {
                        seasonSelect.add(new Option(`Сезон ${seasonNum}`, seasonNum));
                    }
                }

                // Обновляем серии при смене сезона
                seasonSelect.addEventListener('change', updateEpisodes);
                updateEpisodes();

            } else {
                seriesParams.style.display = 'none';
                movieParams.style.display = 'block';
            }
        }

        function updateEpisodes() {
            const selectedSeason = seasonSelect.value;
            episodeSelect.innerHTML = '';

            if (analysisData.series_info && analysisData.series_info[selectedSeason]) {
                const episodes = analysisData.series_info[selectedSeason].episode_list;
                if (episodes) {
                    episodes.forEach(epNum => {
                        episodeSelect.add(new Option(`Серия ${epNum}`, epNum));
                    });
                }
            }
        }

        btnStartDownload.addEventListener('click', () => {
            const url = hdrezkaUrlInput.value;
            const proxy = proxyInput.value;
            let params = { url, proxy };

            const isSeries = seriesParams.style.display === 'block';

            if (isSeries) {
                params.season = seasonSelect.value;
                params.episode = episodeSelect.value;
                params.translator_id = translatorSelect.value;
                params.quality = qualitySelect.value;
            } else {
                params.translator_id = translatorMovieSelect.value;
                params.quality = qualityMovieSelect.value;
            }
            
            // Логика для step-3, step-4, step-5 ...
            // (здесь будет код для запуска воркфлоу и отслеживания прогресса)
            console.log("Starting workflow with params:", params);
            
            const step3 = document.getElementById('step-3');
            const downloadStatus = document.getElementById('download-status');
            const progressFill = document.getElementById('progress-fill');
            const progressText = document.getElementById('progress-text');

            step3.style.display = 'block';
            downloadStatus.textContent = 'Запуск задачи...';
            downloadStatus.className = 'status-message info';
            btnStartDownload.disabled = true;

            fetch('/api/workflow/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(params),
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    downloadStatus.textContent = 'Задача запущена. ID: ' + data.task_id;
                    downloadStatus.className = 'status-message success';
                    pollTaskStatus(data.task_id);
                } else {
                    downloadStatus.textContent = `Ошибка запуска: ${data.error}`;
                    downloadStatus.className = 'status-message error';
                    btnStartDownload.disabled = false;
                }
            })
            .catch(error => {
                downloadStatus.textContent = `Ошибка сети: ${error}`;
                downloadStatus.className = 'status-message error';
                btnStartDownload.disabled = false;
            });
        });

        function pollTaskStatus(taskId) {
            const interval = setInterval(() => {
                fetch(`/api/workflow/status/${taskId}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            const task = data.task;
                            const progressFill = document.getElementById('progress-fill');
                            const progressText = document.getElementById('progress-text');

                            progressFill.style.width = `${task.progress}%`;
                            progressText.textContent = `${task.status}: ${task.message} (${task.progress}%)`;

                            if (task.status === 'COMPLETED' || task.status === 'FAILED') {
                                clearInterval(interval);
                                btnStartDownload.disabled = false;
                                 if (task.status === 'COMPLETED') {
                                    // Показываем следующие шаги
                                }
                            }
                        } else {
                            clearInterval(interval);
                            btnStartDownload.disabled = false;
                        }
                    })
                    .catch(() => {
                        clearInterval(interval);
                        btnStartDownload.disabled = false;
                    });
            }, 2000);
        }
    }
});
