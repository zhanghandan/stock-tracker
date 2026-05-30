/**
 * 股票搜索栏
 */
import React, { useState, useCallback } from 'react';
import { AutoComplete, Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { useStockData } from '../hooks/useStockData';
import { useRankingStore, RankingItem } from '../store/rankingStore';

interface Props {
  onSelectStock: (stock: RankingItem) => void;
}

const SearchBar: React.FC<Props> = ({ onSelectStock }) => {
  const [options, setOptions] = useState<{ value: string; label: string; stock: any }[]>([]);
  const [inputValue, setInputValue] = useState('');
  const { searchStock } = useStockData();

  const handleSearch = useCallback(async (value: string) => {
    setInputValue(value);
    if (!value || value.length < 1) {
      setOptions([]);
      return;
    }

    const items = await searchStock(value);
    setOptions(
      items.map((item: any) => ({
        value: `${item.code} ${item.name}`,
        label: (
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>
              <span style={{ fontWeight: 'bold' }}>{item.code}</span>
              <span style={{ marginLeft: 8 }}>{item.name}</span>
            </span>
            <span style={{ color: '#999' }}>
              {item.latest_price?.toFixed(2)}
            </span>
          </div>
        ),
        stock: item,
      }))
    );
  }, [searchStock]);

  const handleSelect = (value: string) => {
    const option = options.find((o) => o.value === value);
    if (option?.stock) {
      onSelectStock({
        code: option.stock.code,
        name: option.stock.name,
        rank: 0,
        latest_price: option.stock.latest_price,
        change_pct: option.stock.change_pct,
        composite_score: 0,
        technical_score: null,
        sentiment_score: null,
        fund_flow_score: null,
        momentum_score: null,
        volume_score: null,
        technical_signal: null,
        volume_ratio: null,
        turnover_rate: null,
        pe_ttm: option.stock.pe_ttm,
        pb: null,
        total_mv: option.stock.total_mv,
        change_60d: null,
        scored_at: null,
      });
      setInputValue('');
      setOptions([]);
    }
  };

  return (
    <AutoComplete
      options={options}
      onSearch={handleSearch}
      onSelect={handleSelect}
      value={inputValue}
      style={{ width: '100%', maxWidth: 300 }}
    >
      <Input
        placeholder="搜索股票代码或名称..."
        prefix={<SearchOutlined />}
        allowClear
        onChange={(e) => setInputValue(e.target.value)}
      />
    </AutoComplete>
  );
};

export default SearchBar;
