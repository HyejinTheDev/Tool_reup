document.addEventListener('DOMContentLoaded', () => {
    // Navigation Panel Controller
    const navItems = document.querySelectorAll('.nav-item');
    const panels = document.querySelectorAll('.content-panel');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = item.getAttribute('data-target');
            
            navItems.forEach(i => i.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));
            
            item.classList.add('active');
            document.getElementById(targetId).classList.add('active');
        });
    });

    // Realtime SSE Logs Listener
    const logConsole = document.getElementById('log-console');
    const sseSource = new EventSource('/api/logs');

    sseSource.onmessage = (event) => {
        const line = document.createElement('div');
        line.className = 'log-line';
        
        const message = event.data;
        line.innerText = message;
        
        // Colorize lines based on log level tags
        if (message.includes('[ERROR]')) {
            line.classList.add('text-error');
        } else if (message.includes('[SUCCESS]')) {
            line.classList.add('text-success');
        } else if (message.includes('[WARN]')) {
            line.classList.add('text-warning');
        } else if (message.includes('[INFO]') || message.includes('[LOG]')) {
            // Keep default
        }
        
        logConsole.appendChild(line);
        logConsole.scrollTop = logConsole.scrollHeight;
    };

    document.getElementById('btn-clear-logs').addEventListener('click', () => {
        logConsole.innerHTML = '<div class="log-line text-muted">[Hệ thống] Logs đã được xóa. Đang chờ log mới...</div>';
    });

    // Dropzone logic
    const dropzone = document.getElementById('dropzone-area');
    const fileInput = document.getElementById('video-file-input');
    const selectedFileLabel = document.getElementById('selected-file-name');

    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = '#8e2de2';
        dropzone.style.background = 'rgba(142, 45, 226, 0.08)';
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.style.borderColor = 'rgba(142, 45, 226, 0.3)';
        dropzone.style.background = 'rgba(142, 45, 226, 0.02)';
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = 'rgba(142, 45, 226, 0.3)';
        dropzone.style.background = 'rgba(142, 45, 226, 0.02)';
        
        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            if (file.type === 'video/mp4') {
                fileInput.files = e.dataTransfer.files;
                displaySelectedFile(file.name);
                handleVideoPreview(file);
            } else {
                alert('Vui lòng chỉ chọn tệp tin video định dạng .mp4');
            }
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            displaySelectedFile(file.name);
            handleVideoPreview(file);
        }
    });

    function displaySelectedFile(name) {
        selectedFileLabel.innerText = `Đã chọn: ${name}`;
        selectedFileLabel.style.display = 'block';
    }

    function handleVideoPreview(file) {
        if (!file) return;
        const player = document.getElementById('preview-video-player');
        const placeholder = document.getElementById('video-placeholder-screen');
        if (player && placeholder) {
            const url = URL.createObjectURL(file);
            player.src = url;
            player.style.display = 'block';
            placeholder.style.display = 'none';
            player.load();
            player.play();
        }
    }

    // Core Data Fetchers
    let globalAccounts = [];

    async function fetchAccounts() {
        try {
            const res = await fetch('/api/accounts');
            globalAccounts = await res.json();
            if (selectedPlatforms.length === 0 && globalAccounts.length > 0) {
                selectedPlatforms = globalAccounts.map(acc => acc.id);
            }
            renderAccountsList();
            renderPublishPlatforms();
            updateYoutubeFieldsVisibility();
            updateStats();
        } catch (e) {
            console.error('Error fetching accounts:', e);
        }
    }

    async function fetchVideos() {
        try {
            const res = await fetch('/api/videos');
            const videos = await res.json();
            renderVideosTable(videos);
            updateStats();
        } catch (e) {
            console.error('Error fetching videos:', e);
        }
    }

    async function fetchSettings() {
        try {
            const res = await fetch('/api/settings');
            const settings = await res.json();
            document.getElementById('settings-chrome-path').value = settings.chrome_path || '';
            document.getElementById('settings-headless').value = String(settings.headless || false);
        } catch (e) {
            console.error('Error fetching settings:', e);
        }
    }

    function updateStats() {
        document.getElementById('stat-accounts-count').innerText = globalAccounts.length;
        
        fetch('/api/videos')
            .then(res => res.json())
            .then(videos => {
                document.getElementById('stat-videos-count').innerText = videos.length;
                const completedCount = videos.filter(v => v.status === 'completed').length;
                document.getElementById('stat-success-count').innerText = completedCount;
            });
    }

    // Accounts rendering and operations
    const accountsContainer = document.getElementById('accounts-cards-container');

    function renderAccountsList() {
        if (globalAccounts.length === 0) {
            accountsContainer.innerHTML = '<p class="text-muted text-center">Chưa có tài khoản nào được cấu hình.</p>';
            return;
        }

        accountsContainer.innerHTML = globalAccounts.map(acc => {
            const iconMap = {
                youtube: 'fa-youtube',
                tiktok: 'fa-tiktok',
                facebook: 'fa-facebook-f'
            };
            const displayPlatformName = {
                youtube: 'YouTube Shorts',
                tiktok: 'TikTok Studio',
                facebook: 'Facebook Reels'
            };

            return `
                <div class="account-card">
                    <div class="account-info">
                        <div class="platform-badge ${acc.platform}">
                            <i class="fa-brands ${iconMap[acc.platform]}"></i>
                        </div>
                        <div class="account-details">
                            <h4>${acc.name}</h4>
                            <p>${displayPlatformName[acc.platform]} - Profile: ${acc.profile_name}</p>
                        </div>
                    </div>
                    <div class="account-actions">
                        <button class="btn btn-sm btn-outline btn-open-browser" data-id="${acc.id}">
                            <i class="fa-solid fa-window-maximize"></i> Đăng Nhập
                        </button>
                        <button class="btn btn-sm btn-danger btn-delete-account" data-id="${acc.id}">
                            <i class="fa-solid fa-trash-can"></i> Xóa
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        // Bind delete action
        document.querySelectorAll('.btn-delete-account').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.getAttribute('data-id');
                if (confirm('Bạn có chắc chắn muốn xóa tài khoản này khỏi hệ thống?')) {
                    await fetch(`/api/accounts/${id}`, { method: 'DELETE' });
                    fetchAccounts();
                }
            });
        });

        // Bind open browser action
        document.querySelectorAll('.btn-open-browser').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.getAttribute('data-id');
                btn.disabled = true;
                btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang mở...';
                try {
                    const res = await fetch(`/api/accounts/${id}/open-browser`, { method: 'POST' });
                    const data = await res.json();
                    
                    // Allow toggling browser closing
                    btn.innerHTML = '<i class="fa-solid fa-xmark"></i> Đóng Trình Duyệt';
                    btn.disabled = false;
                    btn.classList.remove('btn-outline');
                    btn.classList.add('btn-danger');
                    
                    // Temporarily rebind to close action
                    btn.onclick = async () => {
                        btn.disabled = true;
                        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang đóng...';
                        await fetch(`/api/accounts/${id}/close-browser`, { method: 'POST' });
                        btn.onclick = null; // Unbind
                        fetchAccounts(); // Reset state
                    };
                } catch (e) {
                    console.error(e);
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa-solid fa-window-maximize"></i> Đăng Nhập';
                }
            });
        });
    }

    // Render Platform Avatar badges on Publish page (Buffer Style)
    const composerChannelAvatars = document.getElementById('composer-channel-avatars');
    let selectedPlatforms = [];

    function renderPublishPlatforms() {
        if (!composerChannelAvatars) return;
        
        if (globalAccounts.length === 0) {
            composerChannelAvatars.innerHTML = '<p class="text-muted" style="font-size: 13px;">Vui lòng cấu hình tài khoản trước khi đăng video.</p>';
            return;
        }

        composerChannelAvatars.innerHTML = globalAccounts.map(acc => {
            const iconMap = {
                youtube: 'fa-youtube',
                tiktok: 'fa-tiktok',
                facebook: 'fa-facebook-f'
            };
            
            // Get first character of account name as placeholder
            const initial = acc.name ? acc.name.charAt(0) : 'A';
            const isSelected = selectedPlatforms.includes(acc.id);
            
            return `
                <div class="channel-avatar-badge ${isSelected ? 'selected' : ''}" data-id="${acc.id}" title="${acc.name} (${acc.platform.toUpperCase()})">
                    <div class="channel-avatar-text-placeholder">${initial}</div>
                    <div class="platform-mini-badge ${acc.platform}">
                        <i class="fa-brands ${iconMap[acc.platform]}"></i>
                    </div>
                </div>
            `;
        }).join('');

        // Bind avatar click triggers
        document.querySelectorAll('.channel-avatar-badge').forEach(badge => {
            badge.addEventListener('click', () => {
                const accId = badge.getAttribute('data-id');
                const index = selectedPlatforms.indexOf(accId);
                
                if (index > -1) {
                    selectedPlatforms.splice(index, 1);
                    badge.classList.remove('selected');
                } else {
                    selectedPlatforms.push(accId);
                    badge.classList.add('selected');
                }
                
                // Toggle YouTube specific fields card
                updateYoutubeFieldsVisibility();
                
                // Update live mockup labels based on the first selected account if any
                updateMockupProfileLabels();
            });
        });

        // Bind Select All / Deselect All buttons
        const btnSelectAll = document.getElementById('btn-select-all-channels');
        if (btnSelectAll && !btnSelectAll._bound) {
            btnSelectAll._bound = true;
            btnSelectAll.addEventListener('click', () => {
                selectedPlatforms = globalAccounts.map(acc => acc.id);
                renderPublishPlatforms();
                updateYoutubeFieldsVisibility();
                updateMockupProfileLabels();
            });
        }

        const btnDeselectAll = document.getElementById('btn-deselect-all-channels');
        if (btnDeselectAll && !btnDeselectAll._bound) {
            btnDeselectAll._bound = true;
            btnDeselectAll.addEventListener('click', () => {
                selectedPlatforms = [];
                renderPublishPlatforms();
                updateYoutubeFieldsVisibility();
                updateMockupProfileLabels();
            });
        }
    }

    function updateYoutubeFieldsVisibility() {
        const youtubeFields = document.getElementById('custom-fields-youtube');
        if (youtubeFields) {
            const hasYoutubeSelected = globalAccounts.some(acc => 
                selectedPlatforms.includes(acc.id) && acc.platform === 'youtube'
            );
            youtubeFields.style.display = hasYoutubeSelected ? 'block' : 'none';
        }
        
        const facebookFields = document.getElementById('custom-fields-facebook');
        if (facebookFields) {
            const hasFacebookSelected = globalAccounts.some(acc => 
                selectedPlatforms.includes(acc.id) && acc.platform === 'facebook'
            );
            facebookFields.style.display = hasFacebookSelected ? 'block' : 'none';
        }
        
        // Update YouTube Title preview
        const youtubeTitlePreview = document.getElementById('youtube-title-preview');
        const titleInput = document.getElementById('video-title');
        if (youtubeTitlePreview && titleInput) {
            youtubeTitlePreview.innerText = titleInput.value || 'Tiêu đề YouTube Shorts...';
        }
    }

    function updateMockupProfileLabels() {
        const tiktokUser = document.getElementById('tiktok-user-handle');
        const youtubeChannel = document.getElementById('youtube-channel-name');
        const fbPage = document.getElementById('fb-page-name');

        const activeTiktok = globalAccounts.find(acc => selectedPlatforms.includes(acc.id) && acc.platform === 'tiktok');
        const activeYoutube = globalAccounts.find(acc => selectedPlatforms.includes(acc.id) && acc.platform === 'youtube');
        const activeFb = globalAccounts.find(acc => selectedPlatforms.includes(acc.id) && acc.platform === 'facebook');

        if (tiktokUser) tiktokUser.innerText = activeTiktok ? `@${activeTiktok.name.toLowerCase().replace(/\s/g, '_')}` : '@kenh_tiktok_cua_ban';
        if (youtubeChannel) youtubeChannel.innerText = activeYoutube ? `@${activeYoutube.name}` : '@Kênh_Shorts_Của_Bạn';
        if (fbPage) fbPage.innerText = activeFb ? activeFb.name : 'Kênh Facebook Của Bạn';
    }

    // Render Videos Table
    const videosTableBody = document.getElementById('recent-uploads-list');

    function renderVideosTable(videos) {
        if (videos.length === 0) {
            videosTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Chưa có video nào được tải lên.</td></tr>';
            return;
        }

        // Sort videos: newest first
        videos.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        videosTableBody.innerHTML = videos.map(vid => {
            const statusBadges = {
                pending: '<span class="badge badge-pending">Chờ đăng</span>',
                uploading: '<span class="badge badge-uploading"><i class="fa-solid fa-spinner fa-spin"></i> Đang đăng...</span>',
                completed: '<span class="badge badge-completed">Thành công</span>',
                partial: '<span class="badge badge-partial">Thành công 1 phần</span>',
                failed: '<span class="badge badge-failed">Thất bại</span>'
            };

            const platformIcons = vid.target_accounts.map(accId => {
                const acc = globalAccounts.find(a => a.id === accId);
                if (!acc) return '';
                const iconMap = {
                    youtube: 'fa-youtube youtube',
                    tiktok: 'fa-tiktok tiktok',
                    facebook: 'fa-facebook-f facebook'
                };
                return `<i class="fa-brands ${iconMap[acc.platform]} platform-icon-inline" title="${acc.name}"></i>`;
            }).join(' ');

            return `
                <tr>
                    <td><strong>${vid.filename}</strong></td>
                    <td>${vid.title}</td>
                    <td>${platformIcons}</td>
                    <td>${statusBadges[vid.status]}</td>
                    <td>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <button class="btn btn-sm btn-primary btn-run-publish" data-id="${vid.id}" ${vid.status === 'uploading' ? 'disabled' : ''} title="Bắt đầu tự động đăng bài">
                                <i class="fa-solid fa-play"></i> Đăng bài
                            </button>
                            
                            <!-- Dropdown Xóa bài đã đăng -->
                            <div class="delete-dropdown-container" style="position: relative; display: inline-block;">
                                <button class="btn btn-sm btn-danger btn-toggle-delete-menu" data-id="${vid.id}" title="Tùy chọn xóa video">
                                    <i class="fa-solid fa-trash-can"></i> Xóa <i class="fa-solid fa-caret-down"></i>
                                </button>
                                <div class="delete-dropdown-menu" id="delete-menu-${vid.id}" style="display: none; position: absolute; right: 0; top: 32px; background: #1a1c29; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; z-index: 100; min-width: 180px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); padding: 5px 0;">
                                    <a href="#" class="delete-opt-all" data-id="${vid.id}" style="display: block; padding: 8px 12px; color: #fff; text-decoration: none; font-size: 12px; font-weight: 500; border-bottom: 1px solid rgba(255,255,255,0.05); transition: background 0.2s;">Xóa trên tất cả kênh</a>
                                    ${
                                        vid.target_accounts.map(accId => {
                                            const acc = globalAccounts.find(a => a.id === accId);
                                            if (!acc) return '';
                                            return `<a href="#" class="delete-opt-channel" data-video-id="${vid.id}" data-account-id="${acc.id}" style="display: block; padding: 8px 12px; color: var(--text-muted); text-decoration: none; font-size: 11px; transition: background 0.2s;">Gỡ trên ${acc.name} (${acc.platform.toUpperCase()})</a>`;
                                        }).join('')
                                    }
                                    <a href="#" class="delete-opt-local" data-id="${vid.id}" style="display: block; padding: 8px 12px; color: #ff8a80; text-decoration: none; font-size: 12px; font-weight: 500; border-top: 1px solid rgba(255,255,255,0.05); transition: background 0.2s;">Chỉ xóa bản ghi cục bộ</a>
                                </div>
                            </div>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        // Bind play buttons
        document.querySelectorAll('.btn-run-publish').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.getAttribute('data-id');
                btn.disabled = true;
                
                // Show dashboard panel to monitor logs
                document.querySelector('[data-target="panel-dashboard"]').click();
                
                const res = await fetch(`/api/videos/${id}/publish`, { method: 'POST' });
                const data = await res.json();
                
                fetchVideos();
            });
        });

        // Bind dropdown menu toggles
        document.querySelectorAll('.btn-toggle-delete-menu').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.getAttribute('data-id');
                const menu = document.getElementById(`delete-menu-${id}`);
                
                // Hide all other open delete menus first
                document.querySelectorAll('.delete-dropdown-menu').forEach(m => {
                    if (m.id !== `delete-menu-${id}`) m.style.display = 'none';
                });
                
                // Toggle current
                menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
            });
        });

        // Hide menus when clicking elsewhere
        window.addEventListener('click', () => {
            document.querySelectorAll('.delete-dropdown-menu').forEach(m => {
                m.style.display = 'none';
            });
        });

        // Bind 'Xóa trên tất cả các kênh' click
        document.querySelectorAll('.delete-opt-all').forEach(link => {
            link.addEventListener('click', async (e) => {
                e.preventDefault();
                const videoId = link.getAttribute('data-id');
                
                if (confirm('Bạn có chắc chắn muốn gỡ video này khỏi tất cả các kênh đã đăng và xóa bản ghi cục bộ? Robot sẽ mở trình duyệt tự động thực hiện.')) {
                    document.querySelector('[data-target="panel-dashboard"]').click();
                    
                    const vid = videos.find(v => v.id == videoId);
                    const accountIds = vid ? vid.target_accounts : [];
                    
                    const res = await fetch(`/api/videos/${videoId}/delete`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ account_ids: accountIds, delete_record: true })
                    });
                    
                    alert('Đã kích hoạt tiến trình tự động gỡ bài. Vui lòng theo dõi logs trên Console.');
                    fetchVideos();
                }
            });
        });

        // Bind 'Gỡ trên kênh riêng lẻ' click
        document.querySelectorAll('.delete-opt-channel').forEach(link => {
            link.addEventListener('click', async (e) => {
                e.preventDefault();
                const videoId = link.getAttribute('data-video-id');
                const accountId = link.getAttribute('data-account-id');
                const acc = globalAccounts.find(a => a.id === accountId);
                
                if (confirm(`Bạn có chắc chắn muốn gỡ video này trên kênh ${acc ? acc.name : accountId}? Robot sẽ mở trình duyệt tự động thực hiện.`)) {
                    document.querySelector('[data-target="panel-dashboard"]').click();
                    
                    const res = await fetch(`/api/videos/${videoId}/delete`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ account_ids: [accountId], delete_record: false })
                    });
                    
                    alert(`Đã kích hoạt tiến trình gỡ bài trên kênh ${acc ? acc.name : accountId}.`);
                    fetchVideos();
                }
            });
        });

        // Bind 'Chỉ xóa bản ghi cục bộ' click
        document.querySelectorAll('.delete-opt-local').forEach(link => {
            link.addEventListener('click', async (e) => {
                e.preventDefault();
                const videoId = link.getAttribute('data-id');
                
                if (confirm('Bạn có chắc chắn muốn xóa bản ghi này khỏi cơ sở dữ liệu? (Video đã đăng trên các mạng xã hội sẽ KHÔNG bị gỡ)')) {
                    const res = await fetch(`/api/videos/${videoId}/delete`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ account_ids: [], delete_record: true })
                    });
                    
                    fetchVideos();
                }
            });
        });
    }

    // Forms submission handlers
    // 1. Settings Submit
    document.getElementById('form-settings').addEventListener('submit', async (e) => {
        e.preventDefault();
        const chrome_path = document.getElementById('settings-chrome-path').value;
        const headless = document.getElementById('settings-headless').value === 'true';

        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chrome_path, headless })
        });
        const data = await res.json();
        if (data.success) {
            alert('Lưu cấu hình hệ thống thành công!');
            fetchSettings();
        }
    });

    // 2. Add Account Submit
    document.getElementById('form-add-account').addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('acc-name').value;
        const platform = document.getElementById('acc-platform').value;

        const res = await fetch('/api/accounts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, platform })
        });
        
        if (res.ok) {
            document.getElementById('acc-name').value = '';
            fetchAccounts();
            alert('Đã thêm tài khoản thành công! Nhấn nút "Đăng nhập" để xác thực.');
        }
    });

    // 2.2. Sync Gmail Accounts Submit
    document.getElementById('btn-sync-gmail').addEventListener('click', async () => {
        const btn = document.getElementById('btn-sync-gmail');
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang đồng bộ...';
        
        try {
            const res = await fetch('/api/accounts/sync-gmail', { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                alert(`Đồng bộ thành công! Đã thêm ${data.added_count} tài khoản từ Gmail Manager.`);
                fetchAccounts();
            } else {
                const errData = await res.json();
                alert(`Lỗi đồng bộ: ${errData.detail || 'Không xác định'}`);
            }
        } catch (e) {
            console.error(e);
            alert('Lỗi kết nối tới máy chủ khi đồng bộ.');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-rotate"></i> Đồng bộ từ Gmail';
        }
    });

    // 3. Publish Video Form Submit
    document.getElementById('form-publish-video').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const file = fileInput.files[0];
        const title = document.getElementById('video-title').value;
        const description = document.getElementById('video-desc').value;
        
        if (selectedPlatforms.length === 0) {
            alert('Vui lòng chọn ít nhất 1 tài khoản để đăng video!');
            return;
        }

        // Validate YouTube title requirement
        const hasYoutube = globalAccounts.some(acc => selectedPlatforms.includes(acc.id) && acc.platform === 'youtube');
        if (hasYoutube && !title.trim()) {
            alert('YouTube Shorts yêu cầu nhập tiêu đề!');
            document.getElementById('video-title').focus();
            return;
        }

        const btnSubmit = document.getElementById('btn-submit-publish');
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang tải file lên server...';

        try {
            const youtubePublishType = document.getElementById('youtube-publish-type')?.value || 'shorts';
            const facebookPublishType = document.getElementById('facebook-publish-type')?.value || 'reels';

            const formData = new FormData();
            formData.append('video', file);
            formData.append('title', title || 'Video Upload'); // Fallback title
            formData.append('description', description);
            formData.append('platforms', JSON.stringify(selectedPlatforms));
            formData.append('publish_type_youtube', youtubePublishType);
            formData.append('publish_type_facebook', facebookPublishType);

            const res = await fetch('/api/videos', {
                method: 'POST',
                body: formData
            });

            if (res.ok) {
                const videoRecord = await res.json();
                
                // Clear form inputs
                fileInput.value = '';
                selectedFileLabel.style.display = 'none';
                document.getElementById('video-title').value = '';
                document.getElementById('video-desc').value = '';
                
                if (document.getElementById('youtube-publish-type')) document.getElementById('youtube-publish-type').value = 'shorts';
                if (document.getElementById('facebook-publish-type')) document.getElementById('facebook-publish-type').value = 'reels';

                // Reset selected platforms
                selectedPlatforms = [];
                renderPublishPlatforms();
                updateYoutubeFieldsVisibility();
                
                // Reset Video Preview Player
                const player = document.getElementById('preview-video-player');
                const placeholder = document.getElementById('video-placeholder-screen');
                if (player && placeholder) {
                    player.style.display = 'none';
                    player.src = '';
                    placeholder.style.display = 'flex';
                }
                
                // Reset text previews
                document.getElementById('tiktok-caption-preview').innerText = 'Nội dung caption TikTok sẽ hiển thị trực quan tại đây...';
                document.getElementById('youtube-caption-preview').innerText = 'Mô tả chi tiết sẽ hiển thị tại đây...';
                document.getElementById('youtube-title-preview').innerText = 'Tiêu đề YouTube Shorts...';
                document.getElementById('fb-caption-preview').innerText = 'Nội dung thước phim Reels của bạn...';
                document.getElementById('char-count').innerText = '0';

                // Notify publishing task trigger
                alert('Tải file lên máy chủ thành công. Nhấn OK để kích hoạt tự động đăng bài.');
                
                // Trigger auto publishing task
                const publishRes = await fetch(`/api/videos/${videoRecord.id}/publish`, { method: 'POST' });
                
                // Redirect to dashboard
                document.querySelector('[data-target="panel-dashboard"]').click();
                fetchVideos();
            } else {
                alert('Lỗi tải video lên máy chủ.');
            }
        } catch (err) {
            console.error(err);
            alert('Đã xảy ra lỗi trong quá trình tải video.');
        } finally {
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Tải lên &amp; Tự động đăng bài ngay';
        }
    });

    // 4. Live Preview Platform Tab Switching
    document.querySelectorAll('.preview-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.preview-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            const platform = tab.getAttribute('data-preview-platform');
            document.querySelectorAll('.mockup-overlay').forEach(o => o.classList.remove('active'));
            document.getElementById(`overlay-${platform}`).classList.add('active');
        });
    });

    // 5. Input Synchronization & Char Counter
    const videoDescInput = document.getElementById('video-desc');
    const charCountSpan = document.getElementById('char-count');
    
    const tiktokCaptionPreview = document.getElementById('tiktok-caption-preview');
    const youtubeCaptionPreview = document.getElementById('youtube-caption-preview');
    const fbCaptionPreview = document.getElementById('fb-caption-preview');
    
    videoDescInput.addEventListener('input', () => {
        const val = videoDescInput.value;
        charCountSpan.innerText = val.length;
        
        tiktokCaptionPreview.innerText = val || 'Nội dung caption TikTok sẽ hiển thị trực quan tại đây...';
        youtubeCaptionPreview.innerText = val || 'Mô tả chi tiết sẽ hiển thị tại đây...';
        fbCaptionPreview.innerText = val || 'Nội dung thước phim Reels của bạn...';
    });
    
    const videoTitleInput = document.getElementById('video-title');
    const youtubeTitlePreview = document.getElementById('youtube-title-preview');
    
    videoTitleInput.addEventListener('input', () => {
        youtubeTitlePreview.innerText = videoTitleInput.value || 'Tiêu đề YouTube Shorts...';
    });

    // 6. Select All / Deselect All Channels
    const btnSelectAll = document.getElementById('btn-select-all-channels');
    const btnDeselectAll = document.getElementById('btn-deselect-all-channels');

    if (btnSelectAll) {
        btnSelectAll.addEventListener('click', () => {
            selectedPlatforms = globalAccounts.map(acc => acc.id);
            document.querySelectorAll('.channel-avatar-badge').forEach(badge => {
                badge.classList.add('selected');
            });
            updateYoutubeFieldsVisibility();
            updateMockupProfileLabels();
        });
    }

    if (btnDeselectAll) {
        btnDeselectAll.addEventListener('click', () => {
            selectedPlatforms = [];
            document.querySelectorAll('.channel-avatar-badge').forEach(badge => {
                badge.classList.remove('selected');
            });
            updateYoutubeFieldsVisibility();
            updateMockupProfileLabels();
        });
    }

    // Initial Setup Runs
    fetchAccounts();
    fetchVideos();
    fetchSettings();
    
    // Refresh videos state periodically
    setInterval(fetchVideos, 10000);
});
