import React, { useState, useEffect } from 'react';
import { ArrowUp, ArrowDown, Download, Search, RefreshCw, AlertCircle } from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

const Dashboard = () => {
    const [stockData, setStockData] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Search & Filter
    const [searchTerm, setSearchTerm] = useState('');

    // Pagination
    const [currentPage, setCurrentPage] = useState(1);
    const [itemsPerPage] = useState(20);

    // Sorting
    const [sortConfig, setSortConfig] = useState({ key: 'score', direction: 'desc' });

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(`${API_BASE_URL}/scan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tickers: [] }) // Empty list = Scan All
            });

            if (!response.ok) throw new Error('Failed to fetch data');

            const data = await response.json();
            setStockData(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleExport = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/export`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(stockData) // Export current full dataset
            });

            if (!response.ok) throw new Error('Export failed');

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `momentum_scan_${new Date().toISOString().slice(0, 10)}.xlsx`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        } catch (err) {
            alert('Export failed: ' + err.message);
        }
    };

    // -- Sorting & Filtering Logic --
    const sortedData = React.useMemo(() => {
        let sortableItems = [...stockData];
        if (sortConfig !== null) {
            sortableItems.sort((a, b) => {
                if (a[sortConfig.key] < b[sortConfig.key]) {
                    return sortConfig.direction === 'ascending' ? -1 : 1;
                }
                if (a[sortConfig.key] > b[sortConfig.key]) {
                    return sortConfig.direction === 'ascending' ? 1 : -1;
                }
                return 0;
            });
        }
        return sortableItems;
    }, [stockData, sortConfig]);

    const filteredData = sortedData.filter(item =>
        item.ticker.toLowerCase().includes(searchTerm.toLowerCase())
    );

    // -- Pagination Logic --
    const indexOfLastItem = currentPage * itemsPerPage;
    const indexOfFirstItem = indexOfLastItem - itemsPerPage;
    const currentItems = filteredData.slice(indexOfFirstItem, indexOfLastItem);
    const totalPages = Math.ceil(filteredData.length / itemsPerPage);

    const requestSort = (key) => {
        let direction = 'ascending';
        if (sortConfig.key === key && sortConfig.direction === 'ascending') {
            direction = 'descending';
        }
        setSortConfig({ key, direction });
    };

    const getClassForValue = (val) => {
        if (val > 0) return 'text-green-500';
        if (val < 0) return 'text-red-500';
        return 'text-gray-400';
    };

    const getClassForSignal = (sig) => {
        if (sig === 'BUY') return 'bg-green-600 text-white';
        if (sig === 'SELL') return 'bg-red-600 text-white';
        return 'bg-gray-700 text-gray-300';
    };

    return (
        <div className="min-h-screen bg-gray-900 text-white p-6 font-sans">
            <header className="mb-8 flex flex-col md:flex-row justify-between items-center gap-4">
                <div>
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-orange-400 to-red-500">
                        Momentum Explorer <span className="text-xs text-gray-500 ml-2">BIST ALL EDITION</span>
                    </h1>
                    <p className="text-gray-400 text-sm mt-1">Real-time Technical Analysis & Scoring</p>
                </div>

                <div className="flex gap-3">
                    <button
                        onClick={fetchData}
                        disabled={loading}
                        className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg border border-gray-700 transition"
                    >
                        <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
                        {loading ? "Scanning..." : "Refetch Data"}
                    </button>

                    <button
                        onClick={handleExport}
                        className="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-700 rounded-lg font-medium transition shadow-lg shadow-orange-900/20"
                    >
                        <Download size={18} />
                        Export Excel
                    </button>
                </div>
            </header>

            {/* Stats / Filter Bar */}
            <div className="bg-gray-800 rounded-xl p-4 mb-6 flex flex-col md:flex-row justify-between items-center gap-4 border border-gray-700">
                <div className="items-center flex gap-4">
                    <div className="text-sm text-gray-400">Total Stocks: <span className="text-white font-bold">{stockData.length}</span></div>
                    <div className="text-sm text-gray-400">Showing: <span className="text-white font-bold">{filteredData.length}</span></div>
                </div>

                <div className="relative w-full md:w-64">
                    <Search className="absolute left-3 top-2.5 text-gray-500" size={18} />
                    <input
                        type="text"
                        placeholder="Search Ticker..."
                        value={searchTerm}
                        onChange={(e) => { setSearchTerm(e.target.value); setCurrentPage(1); }}
                        className="w-full bg-gray-900 border border-gray-700 text-white pl-10 pr-4 py-2 rounded-lg focus:outline-none focus:border-orange-500 transition"
                    />
                </div>
            </div>

            {error && (
                <div className="bg-red-900/20 border border-red-500 text-red-200 p-4 rounded-lg mb-6 flex items-center gap-2">
                    <AlertCircle size={20} />
                    {error}
                </div>
            )}

            {/* Main Table */}
            <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden shadow-2xl">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-gray-900/50 text-gray-400 text-sm uppercase tracking-wider border-b border-gray-700">
                                <th
                                    className="p-4 cursor-pointer hover:text-white transition"
                                    onClick={() => requestSort('ticker')}
                                >
                                    Ticker {sortConfig.key === 'ticker' && (sortConfig.direction === 'ascending' ? '▲' : '▼')}
                                </th>
                                <th
                                    className="p-4 cursor-pointer hover:text-white transition text-right"
                                    onClick={() => requestSort('price')}
                                >
                                    Price
                                </th>
                                <th
                                    className="p-4 cursor-pointer hover:text-white transition text-right"
                                    onClick={() => requestSort('change_1d')}
                                >
                                    Daily %
                                </th>
                                <th className="p-4 text-right hidden md:table-cell">3D %</th>
                                <th className="p-4 text-right hidden md:table-cell">5D %</th>
                                <th
                                    className="p-4 cursor-pointer hover:text-white transition text-right"
                                    onClick={() => requestSort('rsi_daily')}
                                >
                                    RSI (14)
                                </th>
                                <th className="p-4 text-right hidden md:table-cell">MA5 Dist%</th>
                                <th
                                    className="p-4 cursor-pointer hover:text-white transition text-right"
                                    onClick={() => requestSort('score')}
                                >
                                    Score
                                </th>
                                <th className="p-4 text-center">Signal</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-700">
                            {loading && stockData.length === 0 ? (
                                <tr>
                                    <td colSpan="9" className="p-12 text-center text-gray-500 animate-pulse">
                                        Scanning Borsa Istanbul... Please wait...
                                    </td>
                                </tr>
                            ) : currentItems.length > 0 ? (
                                currentItems.map((stock) => (
                                    <tr key={stock.ticker} className="hover:bg-gray-700/50 transition">
                                        <td className="p-4 font-bold text-orange-400">{stock.ticker}</td>
                                        <td className="p-4 text-right font-mono">{stock.price.toFixed(2)}</td>
                                        <td className={`p-4 text-right font-bold ${getClassForValue(stock.change_1d)}`}>
                                            {stock.change_1d > 0 ? '+' : ''}{stock.change_1d}%
                                        </td>
                                        <td className={`p-4 text-right font-mono hidden md:table-cell ${getClassForValue(stock.change_3d)}`}>
                                            {stock.change_3d}%
                                        </td>
                                        <td className={`p-4 text-right font-mono hidden md:table-cell ${getClassForValue(stock.change_5d)}`}>
                                            {stock.change_5d}%
                                        </td>
                                        <td className={`p-4 text-right font-mono font-medium ${stock.rsi_daily < 30 ? 'text-green-400' : stock.rsi_daily > 70 ? 'text-red-400' : 'text-blue-300'}`}>
                                            {stock.rsi_daily}
                                        </td>
                                        <td className={`p-4 text-right font-mono hidden md:table-cell ${getClassForValue(stock.dist_ma5)}`}>
                                            {stock.dist_ma5}%
                                        </td>
                                        <td className="p-4 text-right font-bold text-white">
                                            <div className="inline-block bg-gray-900 rounded px-2 py-1 border border-gray-600">
                                                {stock.score}
                                            </div>
                                        </td>
                                        <td className="p-4 text-center">
                                            <span className={`px-2 py-1 rounded text-xs font-bold tracking-wide ${getClassForSignal(stock.signal)}`}>
                                                {stock.signal}
                                            </span>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan="9" className="p-8 text-center text-gray-500">
                                        {loading ? "Refreshing..." : "No stocks found."}
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Pagination Controls */}
                <div className="bg-gray-900 border-t border-gray-700 p-4 flex justify-between items-center">
                    <button
                        onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                        disabled={currentPage === 1}
                        className="px-4 py-2 bg-gray-800 rounded disabled:opacity-50 hover:bg-gray-700 transition text-sm"
                    >
                        Previous
                    </button>
                    <span className="text-gray-400 text-sm">
                        Page <span className="text-white font-bold">{currentPage}</span> of {totalPages}
                    </span>
                    <button
                        onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                        disabled={currentPage === totalPages || totalPages === 0}
                        className="px-4 py-2 bg-gray-800 rounded disabled:opacity-50 hover:bg-gray-700 transition text-sm"
                    >
                        Next
                    </button>
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
