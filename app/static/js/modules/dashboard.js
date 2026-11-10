/**
 * Coffee Shop SME - Modern Dashboard Charts Controller
 * Manages Orders Trend (Today, Week, Month, Year) & Inventory Stock Levels Visualization
 * Fully Responsive across Desktop, Tablet, and Mobile devices.
 */

(function () {
  'use strict';

  // Read initial server-rendered data
  const dataScript = document.getElementById('initialChartData');
  if (!dataScript) return;

  let initialData = {};
  try {
    initialData = JSON.parse(dataScript.textContent || '{}');
  } catch (err) {
    console.error('Failed to parse initial dashboard data:', err);
    return;
  }

  const ordersData = initialData.orders || {};
  const stockData = initialData.stock || {};

  function initCharts() {
    if (typeof Chart === 'undefined') {
      setTimeout(initCharts, 50);
      return;
    }

    // Default typography matching artisan typography
    Chart.defaults.font.family = "'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif";
    Chart.defaults.color = '#75685e';

    initOrdersChart(ordersData);
    initStockChart(stockData);

    // Global resize handler to ensure responsive chart redraw
    let resizeTimer = null;
    window.addEventListener('resize', function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        if (ordersChartInstance) {
          ordersChartInstance.resize();
        }
        if (stockChartInstance) {
          stockChartInstance.resize();
        }
      }, 80);
    });
  }

  let ordersChartInstance = null;

  function initOrdersChart(data) {
    const canvas = document.getElementById('ordersChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    // Create soft warm gradient for orders volume fill
    const gradient = ctx.createLinearGradient(0, 0, 0, 180);
    gradient.addColorStop(0, 'rgba(169, 111, 50, 0.22)');
    gradient.addColorStop(1, 'rgba(169, 111, 50, 0.01)');

    ordersChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.labels || [],
        datasets: [
          {
            label: 'Orders Count',
            data: data.orders || [],
            borderColor: '#a96f32',
            backgroundColor: gradient,
            borderWidth: 2.2,
            fill: true,
            tension: 0.35,
            pointBackgroundColor: '#a96f32',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointRadius: window.innerWidth < 600 ? 3 : 4,
            pointHoverRadius: 6,
            pointHitRadius: 15,
            yAxisID: 'yOrders'
          },
          {
            label: 'Revenue (₱)',
            data: data.revenue || [],
            borderColor: '#543b27',
            borderDash: [5, 4],
            borderWidth: 1.8,
            fill: false,
            tension: 0.35,
            pointBackgroundColor: '#543b27',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 1.5,
            pointRadius: window.innerWidth < 600 ? 2.5 : 3,
            pointHoverRadius: 5,
            pointHitRadius: 15,
            yAxisID: 'yRevenue'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        resizeDelay: 60,
        interaction: {
          mode: 'index',
          intersect: false
        },
        plugins: {
          legend: {
            display: true,
            position: 'top',
            align: 'end',
            labels: {
              boxWidth: 9,
              boxHeight: 9,
              usePointStyle: true,
              pointStyle: 'circle',
              font: { size: window.innerWidth < 600 ? 10 : 11, weight: '500' },
              color: '#55483d',
              padding: 10
            }
          },
          tooltip: {
            backgroundColor: '#261b13',
            titleColor: '#fbf8f5',
            titleFont: { size: 12, weight: '600' },
            bodyColor: '#e5ded6',
            bodyFont: { size: 11 },
            borderColor: 'rgba(255, 255, 255, 0.08)',
            borderWidth: 1,
            padding: 9,
            cornerRadius: 7,
            callbacks: {
              label: function (context) {
                const datasetLabel = context.dataset.label || '';
                const val = context.parsed.y;
                if (context.datasetIndex === 0) {
                  return ` ${datasetLabel}: ${val} orders`;
                } else {
                  return ` ${datasetLabel}: ₱${Number(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                }
              }
            }
          }
        },
        scales: {
          x: {
            grid: {
              display: false
            },
            ticks: {
              font: { size: window.innerWidth < 600 ? 9.5 : 10.5 },
              color: '#85786d',
              autoSkip: true,
              maxTicksLimit: window.innerWidth < 600 ? 6 : 9,
              maxRotation: 0
            }
          },
          yOrders: {
            type: 'linear',
            position: 'left',
            beginAtZero: true,
            ticks: {
              precision: 0,
              font: { size: 10 },
              color: '#85786d'
            },
            grid: {
              color: 'rgba(0, 0, 0, 0.04)',
              drawBorder: false
            }
          },
          yRevenue: {
            type: 'linear',
            position: 'right',
            beginAtZero: true,
            grid: {
              display: false
            },
            ticks: {
              callback: function (val) {
                return '₱' + Number(val).toLocaleString();
              },
              font: { size: 9.5 },
              color: '#a96f32',
              maxTicksLimit: 5
            }
          }
        }
      }
    });

    setupPeriodFilterButtons();
  }

  function setupPeriodFilterButtons() {
    const filterGroup = document.getElementById('ordersFilterGroup');
    if (!filterGroup) return;

    const buttons = filterGroup.querySelectorAll('.filter-segmented-btn');
    const badge = document.getElementById('ordersActivePeriodBadge');
    const totalOrdersEl = document.getElementById('chartTotalOrders');
    const totalRevenueEl = document.getElementById('chartTotalRevenue');
    const avgTicketEl = document.getElementById('chartAvgTicket');

    buttons.forEach((btn) => {
      btn.addEventListener('click', async function () {
        const period = this.getAttribute('data-period');
        if (!period) return;

        buttons.forEach((b) => b.classList.remove('active'));
        this.classList.add('active');

        if (badge) {
          badge.textContent = period.charAt(0).toUpperCase() + period.slice(1);
        }

        try {
          const resp = await fetch(`/api/orders-chart?period=${period}`);
          if (!resp.ok) throw new Error('Network error');
          const data = await resp.json();

          if (totalOrdersEl) totalOrdersEl.textContent = `${data.total_orders} orders`;
          if (totalRevenueEl) totalRevenueEl.textContent = data.formatted_revenue || '₱0.00';
          if (avgTicketEl) avgTicketEl.textContent = data.formatted_avg_ticket || '₱0.00';

          if (ordersChartInstance) {
            ordersChartInstance.data.labels = data.labels || [];
            ordersChartInstance.data.datasets[0].data = data.orders || [];
            ordersChartInstance.data.datasets[1].data = data.revenue || [];
            ordersChartInstance.update();
          }
        } catch (err) {
          console.error('Failed to load orders chart data:', err);
        }
      });
    });
  }

  let stockChartInstance = null;

  function initStockChart(data) {
    const canvas = document.getElementById('stockChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const labels = data.labels || [];
    const stockPct = data.stock_pct || [];
    const currents = data.current || [];
    const reorders = data.reorder || [];
    const units = data.units || [];
    const statuses = data.statuses || [];

    const barColors = stockPct.map((pct, idx) => {
      const st = statuses[idx];
      if (st === 'critical' || pct <= 50) {
        return '#e05252'; // Coral Red
      } else if (st === 'low' || pct <= 100) {
        return '#e29526'; // Warm Amber
      } else {
        return '#3f826d'; // Forest Emerald / Healthy
      }
    });

    const maxVal = Math.max(160, ...stockPct);
    const xMax = Math.ceil(maxVal * 1.15 / 50) * 50;

    stockChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Stock Buffer',
            data: stockPct,
            backgroundColor: barColors,
            borderRadius: 4,
            borderSkipped: false,
            barThickness: window.innerWidth < 600 ? 10 : 13
          }
        ]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        resizeDelay: 60,
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            backgroundColor: '#261b13',
            titleColor: '#fbf8f5',
            titleFont: { size: 12, weight: '600' },
            bodyColor: '#e5ded6',
            bodyFont: { size: 11 },
            borderColor: 'rgba(255, 255, 255, 0.08)',
            borderWidth: 1,
            padding: 9,
            cornerRadius: 7,
            callbacks: {
              label: function (context) {
                const idx = context.dataIndex;
                const curr = currents[idx];
                const reorder = reorders[idx];
                const u = units[idx] || '';
                const pct = stockPct[idx];
                const status = (statuses[idx] || '').toUpperCase();

                return [
                  ` Current: ${curr} ${u}`,
                  ` Reorder Point: ${reorder} ${u}`,
                  ` Buffer: ${pct}% (${status})`
                ];
              }
            }
          }
        },
        scales: {
          x: {
            beginAtZero: true,
            max: xMax,
            grid: {
              color: function (context) {
                if (context.tick.value === 100) {
                  return 'rgba(224, 82, 82, 0.5)';
                }
                return 'rgba(0, 0, 0, 0.04)';
              },
              lineWidth: function (context) {
                return context.tick.value === 100 ? 1.5 : 1;
              }
            },
            ticks: {
              callback: function (val) {
                if (val === 100) return window.innerWidth < 600 ? '100%*' : '100% (Reorder)';
                return val + '%';
              },
              font: { size: 9.5 },
              color: function (context) {
                return context.tick.value === 100 ? '#b83b3b' : '#85786d';
              },
              maxTicksLimit: window.innerWidth < 600 ? 4 : 7
            }
          },
          y: {
            grid: {
              display: false
            },
            ticks: {
              font: { size: window.innerWidth < 600 ? 10 : 11, weight: '500' },
              color: '#3d3027',
              callback: function (val) {
                const label = this.getLabelForValue(val) || '';
                const isMobile = window.innerWidth < 600;
                return isMobile && label.length > 13 ? label.slice(0, 12) + '…' : label;
              }
            }
          }
        }
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCharts);
  } else {
    initCharts();
  }
})();
