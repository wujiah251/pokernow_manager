// ========== Vue 3 应用 ==========
const { createApp, ref, onMounted, watch, nextTick, computed } = Vue;

const app = createApp({
    setup() {
        // ========== 状态 ==========
        const currentTab = ref(0);
        const tabs = ['玩家映射', 'PnL 查询', '对局查询', '数据上传', '数据删除'];

        // 玩家数据
        const players = ref([]);
        const playerList = ref([]);

        // PnL 数据
        const dates = ref([]);
        const selectedDate = ref('');
        const selectedPlayer = ref('');
        const pnlRecords = ref([]);
        const pnlCumulative = ref({});  // 累计PnL
        const pnlSortColumn = ref('total_net');  // 默认按净盈亏排序
        const pnlSortDirection = ref('desc');    // 默认降序
        let pnlChart = null;

        // 曲线多选玩家
        const selectedChartPlayers = ref([]);

        // 排序后的 PnL 记录
        const sortedPnlRecords = computed(() => {
            const records = [...pnlRecords.value];
            const col = pnlSortColumn.value;
            const dir = pnlSortDirection.value;

            records.sort((a, b) => {
                let valA, valB;

                // cumulative_net 需要从 pnlCumulative 映射中获取
                if (col === 'cumulative_net') {
                    valA = pnlCumulative.value[a.player_nickname];
                    valB = pnlCumulative.value[b.player_nickname];
                } else {
                    valA = a[col];
                    valB = b[col];
                }

                // 处理 undefined 或 null
                if (valA === undefined || valA === null) valA = 0;
                if (valB === undefined || valB === null) valB = 0;

                // 数字类型排序
                if (typeof valA === 'number' && typeof valB === 'number') {
                    return dir === 'asc' ? valA - valB : valB - valA;
                }

                // 字符串类型排序
                if (typeof valA === 'string' && typeof valB === 'string') {
                    return dir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
                }

                // 默认
                return 0;
            });
            return records;
        });

        // 合计行数据
        const pnlTotal = computed(() => {
            const records = pnlRecords.value;
            if (!records || records.length === 0) return null;

            let totalNet = 0;
            records.forEach(r => {
                totalNet += (r.total_net || 0);
            });

            return {
                date: '',
                player_nickname: '合计',
                total_net: totalNet,
                cumulative_net: null
            };
        });

        // 切换排序
        const toggleSort = (column) => {
            if (pnlSortColumn.value === column) {
                pnlSortDirection.value = pnlSortDirection.value === 'asc' ? 'desc' : 'asc';
            } else {
                pnlSortColumn.value = column;
                pnlSortDirection.value = (column === 'total_net' || column === 'cumulative_net') ? 'desc' : 'asc';
            }
        };

        // 图表数据
        const chartStartDate = ref('');
        const chartEndDate = ref('');
        const chartPlayer = ref('');

        // 上传数据
        const uploadDate = ref('');
        const selectedFile = ref(null);
        const uploading = ref(false);
        const uploadResult = ref(null);

        // 删除数据
        const deleteStartDate = ref('');
        const deleteEndDate = ref('');
        const deletePnl = ref(true);
        const deleteLedger = ref(true);
        const deleting = ref(false);
        const deleteResult = ref(null);

        // 新增玩家
        const newPlayer = ref({ nickname: '', alias: '' });
        const adding = ref(false);
        const addResult = ref(null);

        // 编辑玩家
        const showEditDialog = ref(false);
        const editPlayer = ref({ nickname: '', alias: '' });
        const saving = ref(false);
        const editResult = ref(null);

        // 合并玩家
        const mergeForm = ref({ oldNickname: '', newNickname: '' });
        const merging = ref(false);
        const mergeResult = ref(null);

        // ========== 计算属性 ==========
        const canDelete = computed(() => {
            return deleteStartDate.value && deleteEndDate.value && (deletePnl.value || deleteLedger.value);
        });

        // ========== 工具函数 ==========
        const formatDate = (dateStr) => {
            if (!dateStr) return '-';
            const date = new Date(dateStr);
            return date.toLocaleDateString('zh-CN');
        };

        const formatMoney = (value) => {
            const num = Number(value);
            if (isNaN(num)) return '0';
            return num.toLocaleString('zh-CN');
        };

        const getPnLClass = (value) => {
            const num = Number(value);
            if (num > 0) return 'positive';
            if (num < 0) return 'negative';
            return '';
        };

        // ========== API 请求 ==========
        const apiGet = async (url) => {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        };

        const apiPost = async (url, data) => {
            const formData = new FormData();
            formData.append('file', data.file);
            formData.append('date', data.date);

            const response = await fetch(url, {
                method: 'POST',
                body: formData
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        };

        // ========== 数据加载 ==========
        const loadPlayers = async () => {
            try {
                // 获取所有参与过游戏的玩家（用于下拉选择）
                playerList.value = await apiGet('/api/players/all');
                // 同时获取玩家映射信息（用于显示）
                players.value = await apiGet('/api/players');
            } catch (error) {
                console.error('加载玩家失败:', error);
            }
        };

        const addPlayer = async () => {
            if (!newPlayer.value.alias || !newPlayer.value.nickname) return;

            adding.value = true;
            addResult.value = null;

            try {
                const response = await fetch('/api/players', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(newPlayer.value)
                });

                const result = await response.json();

                if (result.success) {
                    addResult.value = {
                        success: true,
                        message: '添加成功！'
                    };
                    // 刷新玩家列表
                    await loadPlayers();
                    // 清空表单
                    newPlayer.value = { player_id: '', nickname: '', alias: '' };
                } else {
                    addResult.value = {
                        success: false,
                        message: `添加失败: ${result.error}`
                    };
                }
            } catch (error) {
                addResult.value = {
                    success: false,
                    message: `添加失败: ${error.message}`
                };
            } finally {
                adding.value = false;
            }
        };

        // 合并玩家
        const mergePlayerData = async () => {
            if (!mergeForm.value.oldNickname || !mergeForm.value.newNickname) return;

            // 二次确认
            if (!confirm(`确定要将 "${mergeForm.value.oldNickname}" 的所有历史记录合并到 "${mergeForm.value.newNickname}" 吗？此操作不可恢复！`)) {
                return;
            }

            merging.value = true;
            mergeResult.value = null;

            try {
                const response = await fetch('/api/players/rename', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        old_nickname: mergeForm.value.oldNickname,
                        new_nickname: mergeForm.value.newNickname
                    })
                });

                const result = await response.json();

                if (result.success) {
                    mergeResult.value = {
                        success: true,
                        message: `合并成功！更新了 ${result.updated} 条记录`
                    };
                    // 刷新玩家列表
                    await loadPlayers();
                    // 清空表单
                    mergeForm.value = { oldNickname: '', newNickname: '' };
                } else {
                    mergeResult.value = {
                        success: false,
                        message: `合并失败: ${result.error}`
                    };
                }
            } catch (error) {
                mergeResult.value = {
                    success: false,
                    message: `合并失败: ${error.message}`
                };
            } finally {
                merging.value = false;
            }
        };

        // 删除玩家映射
        const deletePlayerMapping = async (nickname) => {
            if (!confirm(`确定要删除玩家 "${nickname}" 的映射吗？`)) {
                return;
            }

            try {
                const response = await fetch(`/api/players/${encodeURIComponent(nickname)}`, {
                    method: 'DELETE'
                });

                const result = await response.json();

                if (result.success) {
                    alert('删除成功！');
                    // 刷新玩家列表
                    await loadPlayers();
                } else {
                    alert(`删除失败: ${result.error}`);
                }
            } catch (error) {
                alert(`删除失败: ${error.message}`);
            }
        };

        const loadDates = async () => {
            try {
                dates.value = await apiGet('/api/dates');
                if (dates.value.length > 0) {
                    // 日期列表是按倒序排列的，第一个是最新的
                    selectedDate.value = dates.value[0];
                    // 图表默认选择全部日期范围
                    chartStartDate.value = dates.value[dates.value.length - 1]; // 最老的日期
                    chartEndDate.value = dates.value[0]; // 最新的日期
                }
            } catch (error) {
                console.error('加载日期失败:', error);
            }
        };

        const loadPnl = async () => {
            if (!selectedDate.value) return;

            try {
                let url = `/api/pnl/${selectedDate.value}`;
                if (selectedPlayer.value) {
                    url += `?player=${encodeURIComponent(selectedPlayer.value)}`;
                }
                pnlRecords.value = await apiGet(url);

                // 加载累计PnL数据
                await loadCumulative();

                // 加载图表数据
                await nextTick();
                loadChart();
            } catch (error) {
                console.error('加载 PnL 失败:', error);
            }
        };

        const loadCumulative = async () => {
            if (!selectedDate.value) return;

            try {
                const url = `/api/pnl/cumulative/to/${selectedDate.value}`;
                const data = await apiGet(url);

                // 转换为 player_nickname -> cumulative_net 的映射
                const cumMap = {};
                data.forEach(d => {
                    cumMap[d.player_nickname] = d.cumulative_net;
                });
                pnlCumulative.value = cumMap;
            } catch (error) {
                console.error('加载累计PnL失败:', error);
            }
        };

        const loadChart = async () => {
            if (!chartStartDate.value || !chartEndDate.value) return;

            try {
                const startDate = chartStartDate.value;
                const endDate = chartEndDate.value;

                const chartDom = document.getElementById('pnlChart');
                if (!chartDom) return;

                if (pnlChart) {
                    pnlChart.dispose();
                }
                pnlChart = echarts.init(chartDom);

                // 如果有选中的玩家，使用多选API
                if (selectedChartPlayers.value && selectedChartPlayers.value.length > 0) {
                    const url = `/api/pnl/range/selected?start=${startDate}&end=${endDate}&players=${encodeURIComponent(selectedChartPlayers.value.join(','))}`;
                    const result = await apiGet(url);

                    if (!result || !result.dates || result.dates.length === 0) {
                        pnlChart.setOption({
                            title: { text: '暂无数据', left: 'center' }
                        });
                        return;
                    }

                    const dates = result.dates;
                    const players = result.players;

                    // 按累计pnl排序（从大到小）
                    const playerTotals = [];
                    for (const [player, records] of Object.entries(players)) {
                        const total = records.length > 0 ? records[records.length - 1].cumulative_net : 0;
                        playerTotals.push({ player, total });
                    }
                    playerTotals.sort((a, b) => b.total - a.total);
                    const sortedPlayers = playerTotals.map(p => p.player);

                    // 为每个玩家生成一条曲线
                    const series = sortedPlayers.map((player) => {
                        const playerRecords = players[player] || [];
                        // 构建日期到累计值的映射
                        const dateToValue = {};
                        playerRecords.forEach(r => {
                            dateToValue[r.date] = r.cumulative_net;
                        });

                        // 用日期顺序填充数据，缺失日期用 null
                        const data = dates.map(d => dateToValue[d] ?? null);

                        return {
                            name: player,
                            type: 'line',
                            smooth: true,
                            symbol: 'circle',
                            symbolSize: 6,
                            data: data
                        };
                    });

                    pnlChart.setOption({
                        title: {
                            text: '选定玩家累计盈亏曲线',
                            left: 'center',
                            textStyle: { fontFamily: "'Playfair Display', serif", fontSize: 18 }
                        },
                        tooltip: {
                            trigger: 'axis',
                            backgroundColor: 'rgba(13, 77, 43, 0.9)',
                            textStyle: { fontFamily: "'Source Sans 3', sans-serif", color: '#fff' },
                            formatter: (params) => {
                                let html = `${params[0].name}<br/>`;
                                params.forEach(p => {
                                    if (p.value !== null && p.value !== undefined) {
                                        html += `${p.marker} ${p.seriesName}: <b>${p.value.toLocaleString('zh-CN')}</b><br/>`;
                                    }
                                });
                                return html;
                            }
                        },
                        legend: {
                            type: 'scroll',
                            bottom: 10,
                            textStyle: { fontFamily: "'Source Sans 3', sans-serif", fontSize: 12 },
                            data: sortedPlayers
                        },
                        grid: { left: 60, right: 40, top: 60, bottom: 80 },
                        xAxis: {
                            type: 'category',
                            data: dates,
                            boundaryGap: false,
                            axisLine: { lineStyle: { color: '#ddd' } },
                            axisLabel: { color: '#888', fontFamily: "'Source Sans 3', sans-serif" }
                        },
                        yAxis: {
                            type: 'value',
                            axisLine: { show: false },
                            splitLine: { lineStyle: { color: 'rgba(0,0,0,0.05)' } },
                            axisLabel: {
                                color: '#888',
                                fontFamily: "'Source Sans 3', sans-serif",
                                formatter: (v) => v.toLocaleString('zh-CN')
                            }
                        },
                        series: series
                    });
                } else if (chartPlayer.value) {
                    // 选择特定玩家：使用原有 API
                    const url = `/api/pnl/range/cumulative?start=${startDate}&end=${endDate}&player=${encodeURIComponent(chartPlayer.value)}`;
                    const data = await apiGet(url);

                    if (!data || data.length === 0) {
                        pnlChart.setOption({
                            title: { text: '暂无数据' }
                        });
                        return;
                    }

                    const dates = data.map(d => d.date);
                    const values = data.map(d => d.cumulative_net);

                    pnlChart.setOption({
                        title: {
                            text: `${chartPlayer.value} 累计盈亏曲线`,
                            left: 'center',
                            textStyle: { fontFamily: "'Playfair Display', serif", fontSize: 18 }
                        },
                        tooltip: {
                            trigger: 'axis',
                            backgroundColor: 'rgba(13, 77, 43, 0.9)',
                            textStyle: { fontFamily: "'Source Sans 3', sans-serif", color: '#fff' },
                            formatter: (params) => {
                                const p = params[0];
                                return `${p.name}<br/><b>${p.value.toLocaleString('zh-CN')}</b>`;
                            }
                        },
                        grid: { left: 60, right: 40, top: 60, bottom: 40 },
                        xAxis: {
                            type: 'category',
                            data: dates,
                            axisLine: { lineStyle: { color: '#ddd' } },
                            axisLabel: { color: '#888', fontFamily: "'Source Sans 3', sans-serif" }
                        },
                        yAxis: {
                            type: 'value',
                            axisLine: { show: false },
                            splitLine: { lineStyle: { color: 'rgba(0,0,0,0.05)' } },
                            axisLabel: {
                                color: '#888',
                                fontFamily: "'Source Sans 3', sans-serif",
                                formatter: (v) => v.toLocaleString('zh-CN')
                            }
                        },
                        series: [{
                            name: '累计盈亏',
                            type: 'line',
                            data: values,
                            smooth: true,
                            symbol: 'circle',
                            symbolSize: 8,
                            lineStyle: { color: '#0d4d2b', width: 3 },
                            itemStyle: { color: '#d4af37', borderColor: '#fff', borderWidth: 2 },
                            areaStyle: { color: 'rgba(13, 77, 43, 0.1)' }
                        }]
                    });
                } else {
                    // 未选择玩家：获取所有玩家的数据
                    const url = `/api/pnl/range/all?start=${startDate}&end=${endDate}`;
                    const result = await apiGet(url);

                    if (!result || !result.dates || result.dates.length === 0) {
                        pnlChart.setOption({
                            title: { text: '暂无数据', left: 'center' }
                        });
                        return;
                    }

                    const dates = result.dates;
                    const players = result.players;

                    // 计算每个玩家的总累计pnl
                    const playerTotals = [];
                    for (const [player, records] of Object.entries(players)) {
                        const total = records.length > 0 ? records[records.length - 1].cumulative_net : 0;
                        playerTotals.push({ player, total });
                    }
                    // 按累计pnl从大到小排序
                    playerTotals.sort((a, b) => b.total - a.total);
                    const sortedPlayerNames = playerTotals.map(p => p.player);

                    // 按排序顺序生成曲线
                    const series = sortedPlayerNames.map((player) => {
                        const playerRecords = players[player];
                        // 构建日期到累计值的映射
                        const dateToValue = {};
                        playerRecords.forEach(r => {
                            dateToValue[r.date] = r.cumulative_net;
                        });

                        // 用日期顺序填充数据，缺失日期用 null
                        const data = dates.map(d => dateToValue[d] ?? null);

                        return {
                            name: player,
                            type: 'line',
                            smooth: true,
                            symbol: 'circle',
                            symbolSize: 6,
                            data: data
                        };
                    });

                    pnlChart.setOption({
                        title: {
                            text: '所有玩家累计盈亏曲线',
                            left: 'center',
                            textStyle: { fontFamily: "'Playfair Display', serif", fontSize: 18 }
                        },
                        tooltip: {
                            trigger: 'axis',
                            backgroundColor: 'rgba(13, 77, 43, 0.9)',
                            textStyle: { fontFamily: "'Source Sans 3', sans-serif", color: '#fff' },
                            formatter: (params) => {
                                let html = `${params[0].name}<br/>`;
                                params.forEach(p => {
                                    if (p.value !== null && p.value !== undefined) {
                                        html += `${p.marker} ${p.seriesName}: <b>${p.value.toLocaleString('zh-CN')}</b><br/>`;
                                    }
                                });
                                return html;
                            }
                        },
                        legend: {
                            type: 'scroll',
                            bottom: 10,
                            textStyle: { fontFamily: "'Source Sans 3', sans-serif", fontSize: 12 },
                            data: sortedPlayerNames
                        },
                        grid: { left: 60, right: 40, top: 60, bottom: 80 },
                        xAxis: {
                            type: 'category',
                            data: dates,
                            boundaryGap: false,
                            axisLine: { lineStyle: { color: '#ddd' } },
                            axisLabel: { color: '#888', fontFamily: "'Source Sans 3', sans-serif" }
                        },
                        yAxis: {
                            type: 'value',
                            axisLine: { show: false },
                            splitLine: { lineStyle: { color: 'rgba(0,0,0,0.05)' } },
                            axisLabel: {
                                color: '#888',
                                fontFamily: "'Source Sans 3', sans-serif",
                                formatter: (v) => v.toLocaleString('zh-CN')
                            }
                        },
                        series: series
                    });
                }
            } catch (error) {
                console.error('加载图表失败:', error);
            }
        };

        // ========== 文件上传 ==========
        const handleFileSelect = (event) => {
            const file = event.target.files[0];
            if (file) {
                selectedFile.value = file;
                uploadResult.value = null;
            }
        };

        const uploadFile = async () => {
            if (!selectedFile.value || !uploadDate.value) return;

            uploading.value = true;
            uploadResult.value = null;

            try {
                // 先预检查
                const formData = new FormData();
                formData.append('file', selectedFile.value);

                const checkResponse = await fetch('/api/ledger/precheck', {
                    method: 'POST',
                    body: formData
                });

                const checkResult = await checkResponse.json();

                // 如果有没有映射的玩家，提示用户
                if (checkResult.has_unmapped) {
                    const confirmUpload = confirm(`警告：以下玩家尚未添加到映射表：\n${checkResult.unmapped_players.join(', ')}\n\n是否仍要上传？`);
                    if (!confirmUpload) {
                        uploading.value = false;
                        return;
                    }
                }

                // 重新设置文件指针，因为预检查已经读取了文件
                selectedFile.value = document.getElementById('csvFile').files[0];

                // 上传文件
                const result = await apiPost('/api/ledger/upload', {
                    file: selectedFile.value,
                    date: uploadDate.value
                });

                uploadResult.value = {
                    success: true,
                    message: `上传成功！共导入 ${result.count} 条记录`
                };

                // 刷新日期列表
                await loadDates();

                // 清空表单
                selectedFile.value = null;
                document.getElementById('csvFile').value = '';
            } catch (error) {
                uploadResult.value = {
                    success: false,
                    message: `上传失败: ${error.message}`
                };
            } finally {
                uploading.value = false;
            }
        };

        // ========== 数据删除 ==========
        const deleteRecords = async () => {
            if (!canDelete.value) return;

            // 二次确认
            if (!confirm(`确定要删除 ${deleteStartDate.value} 到 ${deleteEndDate.value} 期间的数据吗？此操作不可恢复！`)) {
                return;
            }

            deleting.value = true;
            deleteResult.value = null;

            try {
                const response = await fetch('/api/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        start_date: deleteStartDate.value,
                        end_date: deleteEndDate.value,
                        delete_pnl: deletePnl.value,
                        delete_ledger: deleteLedger.value
                    })
                });

                const result = await response.json();

                if (result.success) {
                    deleteResult.value = {
                        success: true,
                        message: `删除成功！PnL 记录: ${result.deleted_pnl} 条, 对局记录: ${result.deleted_ledger} 条`
                    };
                    // 刷新日期列表
                    await loadDates();
                } else {
                    deleteResult.value = {
                        success: false,
                        message: `删除失败: ${result.error}`
                    };
                }
            } catch (error) {
                deleteResult.value = {
                    success: false,
                    message: `删除失败: ${error.message}`
                };
            } finally {
                deleting.value = false;
            }
        };

        // ========== 生命周期 ==========
        onMounted(async () => {
            await loadPlayers();
            await loadDates();
        });

        // 监听 Tab 切换
        watch(currentTab, async (newTab) => {
            if (newTab === 1 && dates.value.length > 0) {
                await loadPnl();
                await loadChart();
            }
        });

        return {
            // 状态
            currentTab,
            tabs,
            players,
            playerList,
            dates,
            selectedDate,
            selectedPlayer,
            pnlRecords,
            pnlTotal,
            pnlCumulative,
            sortedPnlRecords,
            pnlSortColumn,
            pnlSortDirection,
            toggleSort,
            chartStartDate,
            chartEndDate,
            chartPlayer,
            selectedChartPlayers,
            uploadDate,
            selectedFile,
            uploading,
            uploadResult,
            deleteStartDate,
            deleteEndDate,
            deletePnl,
            deleteLedger,
            deleting,
            deleteResult,
            canDelete,
            newPlayer,
            adding,
            addResult,
            mergeForm,
            merging,
            mergeResult,

            // 方法
            formatDate,
            formatMoney,
            getPnLClass,
            loadPnl,
            loadChart,
            addPlayer,
            mergePlayerData,
            deletePlayerMapping,
            handleFileSelect,
            uploadFile,
            deleteRecords
        };
    }
});

app.mount('#app');
