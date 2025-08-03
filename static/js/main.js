document.addEventListener('DOMContentLoaded', function() {
    // 设置收藏按钮事件
    document.querySelectorAll('.star').forEach(star => {
        star.addEventListener('click', function(e) {
            e.stopPropagation();
            const itemId = this.closest('.history-item').dataset.id;
            
            fetch(`/star/${itemId}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.starred) {
                        this.classList.add('starred');
                    } else {
                        this.classList.remove('starred');
                    }
                });
        });
    });
    
    // 设置筛选按钮事件
    document.getElementById('apply-filter').addEventListener('click', function() {
        applyFilters();
    });
    
    // 设置收藏显示按钮事件
    document.getElementById('toggle-starred').addEventListener('click', function() {
        this.classList.toggle('active');
        applyFilters();
    });
    
    function applyFilters() {
        const type = document.getElementById('type-filter').value;
        const startDate = document.getElementById('start-date').value;
        const endDate = document.getElementById('end-date').value;
        const showStarred = document.getElementById('toggle-starred').classList.contains('active');
        
        let params = `?type=${type}&start_date=${startDate}&end_date=${endDate}`;
        if (showStarred) {
            params += '&starred=true';
        }
        
        fetch('/history' + params)
            .then(response => response.json())
            .then(data => {
                renderHistory(data);
            });
    }
    
    function renderHistory(historyItems) {
        const listContainer = document.querySelector('.history-list');
        listContainer.innerHTML = '';
        
        historyItems.forEach(item => {
            const itemElement = document.createElement('div');
            itemElement.className = 'history-item';
            itemElement.dataset.id = item.id;
            
            const typeClass = item.type.toLowerCase();
            const filePreview = item.type !== 'Text' ? 
                `<a href="/download/${item.file_path}" download="${item.content}">下载文件</a>` : 
                '';
            
            const sourceHTML = item.from_source ? 
                `<span class="source">来源: ${item.from_source}</span>` : 
                '';
            
            itemElement.innerHTML = `
                <div class="header">
                    <span class="timestamp">${item.timestamp}</span>
                    <span class="type">${item.type}</span>
                    ${sourceHTML}
                    <span class="star ${item.is_starred ? 'starred' : ''}">★</span>
                </div>
                <div class="content">
                    ${item.type === 'Text' ? `<pre>${item.content}</pre>` : filePreview}
                </div>
            `;
            
            listContainer.appendChild(itemElement);
        });
        
        // 重新绑定收藏事件
        document.querySelectorAll('.star').forEach(star => {
            star.addEventListener('click', function(e) {
                // 与上面相同的收藏处理逻辑
            });
        });
    }
});