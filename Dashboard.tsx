import React, { useState, useRef, useEffect } from 'react';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  ScatterChart, Scatter, AreaChart, Area, CartesianGrid,
  XAxis, YAxis, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import './Dashboard.css';

interface Chart {
  id: string;
  type: string;
  title: string;
  description: string;
  data: any[];
  columns: string[];
  config: any;
}

interface DashboardData {
  query: string;
  charts: Chart[];
  insights: string[];
  error?: string;
}

const Dashboard: React.FC = () => {
  const [query, setQuery] = useState('');
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [conversationHistory, setConversationHistory] = useState<Array<{role: string; content: string}>>([]);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [dashboardData]);

  const handleSubmitQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!query.trim()) return;

    setLoading(true);
    
    try {
      const response = await fetch('http://localhost:8000/generate-dashboard', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          conversation_history: conversationHistory,
        }),
      });

      const data = await response.json();
      setDashboardData(data);

      // Update conversation history
      setConversationHistory([
        ...conversationHistory,
        { role: 'user', content: query },
        { role: 'assistant', content: JSON.stringify(data) }
      ]);

      setQuery('');
    } catch (error) {
      console.error('Error:', error);
      setDashboardData({
        query: query,
        charts: [],
        insights: [],
        error: 'Failed to generate dashboard. Please check your API connection.'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCsvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setCsvFile(file);
    setLoading(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://localhost:8000/upload-csv', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      alert(`CSV uploaded successfully!\nTable: ${data.table_name}\nRows: ${data.rows}`);
    } catch (error) {
      console.error('Error uploading CSV:', error);
      alert('Failed to upload CSV file');
    } finally {
      setLoading(false);
    }
  };

  const renderChart = (chart: Chart, index: number) => {
    const { data, columns, type, title, description } = chart;

    if (!data || data.length === 0) {
      return (
        <div key={index} className="chart-container">
          <h3>{title}</h3>
          <p className="error-message">No data available for this chart</p>
        </div>
      );
    }

    const numericColumns = columns.filter(col => {
      const sample = data[0]?.[col];
      return typeof sample === 'number';
    });

    const categoryColumn = columns.find(col => typeof data[0]?.[col] === 'string');

    return (
      <div key={index} className="chart-container">
        <h3>{title}</h3>
        <p className="chart-description">{description}</p>
        
        {type === 'bar' && numericColumns.length > 0 && (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={categoryColumn || columns[0]} angle={-45} textAnchor="end" height={80} />
              <YAxis />
              <Tooltip />
              <Legend />
              {numericColumns.slice(0, 3).map((col, i) => (
                <Bar key={i} dataKey={col} fill={['#8884d8', '#82ca9d', '#ffc658'][i]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        )}

        {type === 'line' && numericColumns.length > 0 && (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={categoryColumn || columns[0]} angle={-45} textAnchor="end" height={80} />
              <YAxis />
              <Tooltip />
              <Legend />
              {numericColumns.slice(0, 3).map((col, i) => (
                <Line key={i} type="monotone" dataKey={col} stroke={['#8884d8', '#82ca9d', '#ffc658'][i]} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}

        {type === 'pie' && numericColumns.length > 0 && (
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={data}
                dataKey={numericColumns[0]}
                nameKey={categoryColumn || columns[0]}
                cx="50%"
                cy="50%"
                outerRadius={100}
                label
              >
                {data.map((_, i) => (
                  <Cell key={`cell-${i}`} fill={['#8884d8', '#82ca9d', '#ffc658', '#ff7c7c', '#8dd1e1'][i % 5]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        )}

        {type === 'area' && numericColumns.length > 0 && (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={categoryColumn || columns[0]} angle={-45} textAnchor="end" height={80} />
              <YAxis />
              <Tooltip />
              <Legend />
              {numericColumns.slice(0, 3).map((col, i) => (
                <Area key={i} type="monotone" dataKey={col} fill={['#8884d8', '#82ca9d', '#ffc658'][i]} stroke={['#8884d8', '#82ca9d', '#ffc658'][i]} />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        )}

        {type === 'scatter' && numericColumns.length >= 2 && (
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={numericColumns[0]} />
              <YAxis dataKey={numericColumns[1]} />
              <Tooltip />
              <Scatter data={data} fill="#8884d8" />
            </ScatterChart>
          </ResponsiveContainer>
        )}

        {type === 'table' && (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  {columns.map(col => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.slice(0, 10).map((row, i) => (
                  <tr key={i}>
                    {columns.map(col => (
                      <td key={`${i}-${col}`}>{row[col]}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>📊 AI-BI Dashboard Generator</h1>
        <p>Transform natural language into interactive dashboards</p>
      </header>

      <div className="main-content">
        <aside className="sidebar">
          <div className="upload-section">
            <h3>Upload Your Data</h3>
            <label className="file-input-label">
              <input
                type="file"
                accept=".csv"
                onChange={handleCsvUpload}
                disabled={loading}
              />
              <span>Choose CSV File</span>
            </label>
            <p className="sidebar-hint">Upload your own CSV to start querying</p>
          </div>

          <div className="query-history">
            <h3>Recent Queries</h3>
            {conversationHistory
              .filter(msg => msg.role === 'user')
              .slice(-5)
              .map((msg, i) => (
                <div
                  key={i}
                  className="history-item"
                  onClick={() => setQuery(msg.content)}
                >
                  {msg.content.substring(0, 50)}...
                </div>
              ))}
          </div>
        </aside>

        <main className="main-panel">
          <form onSubmit={handleSubmitQuery} className="query-form">
            <div className="input-group">
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Ask your question... e.g., 'Show me monthly sales revenue by region'"
                disabled={loading}
                className="query-input"
              />
              <button type="submit" disabled={loading} className="submit-btn">
                {loading ? '⏳ Generating...' : '🔍 Generate'}
              </button>
            </div>
          </form>

          {loading && (
            <div className="loading-state">
              <div className="spinner"></div>
              <p>Analyzing your query and generating dashboard...</p>
            </div>
          )}

          {dashboardData && !loading && (
            <div className="results-section">
              <div className="insights-panel">
                <h2>📈 Key Insights</h2>
                {dashboardData.error ? (
                  <div className="error-message">{dashboardData.error}</div>
                ) : (
                  <ul>
                    {dashboardData.insights.map((insight, i) => (
                      <li key={i}>{insight}</li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="charts-grid">
                {dashboardData.charts.map((chart, i) => renderChart(chart, i))}
              </div>

              <div className="follow-up-section">
                <h3>🔄 Follow-up Questions</h3>
                <p>Ask a follow-up question to refine or filter the dashboard:</p>
                <input
                  type="text"
                  placeholder="e.g., 'Filter to only show the East region' or 'Show me the trend over time'"
                  onChange={e => setQuery(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') handleSubmitQuery(e as any);
                  }}
                  className="followup-input"
                />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </main>
      </div>
    </div>
  );
};

export default Dashboard;