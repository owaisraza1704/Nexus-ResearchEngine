'use client';

import { useState } from 'react';

const SECTION_LINKS = ['General', 'API Configuration', 'Embedding Model', 'Retrieval Defaults', 'Parsing', 'Workspace'];

export default function Settings() {
  const [activeSection, setActiveSection] = useState('General');
  const [topK, setTopK] = useState('8');
  const [chunkSize, setChunkSize] = useState('256');
  const [chunkOverlap, setChunkOverlap] = useState('32');
  const [embeddingModel, setEmbeddingModel] = useState('text-embedding-ada-002');

  return (
    <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
      {/* Sidebar */}
      <div style={{ width: 200, borderRight: '1px solid #1e1e26', padding: '24px 0', overflowY: 'auto', flexShrink: 0 }}>
        <div style={{ padding: '0 16px', marginBottom: 8 }}>
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.8, color: '#55535d', textTransform: 'uppercase' }}>Settings</div>
        </div>
        {SECTION_LINKS.map(s => (
          <button
            key={s}
            onClick={() => setActiveSection(s)}
            style={{
              width: '100%', padding: '8px 16px', background: activeSection === s ? 'rgba(59,158,255,0.08)' : 'transparent',
              border: 'none', borderLeft: activeSection === s ? '2px solid #3b9eff' : '2px solid transparent',
              cursor: 'pointer', fontSize: 13, color: activeSection === s ? '#f0ede8' : '#55535d',
              textAlign: 'left', fontFamily: 'inherit',
            }}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '32px 40px' }}>
        <h2 style={{ fontSize: 20, fontWeight: 300, letterSpacing: -0.3, color: '#f0ede8', margin: '0 0 28px' }}>{activeSection}</h2>

        <div style={{ maxWidth: 560, display: 'flex', flexDirection: 'column', gap: 20 }}>
          {activeSection === 'General' && (
            <>
              <SettingRow label="Workspace Name" value="Research Lab" onChange={() => {}} />
              <SettingRow label="Default Research Mode" value="Grounded Answer" type="select" options={['Grounded Answer', 'Multi-Document', 'Evidence Only']} onChange={() => {}} />
            </>
          )}

          {activeSection === 'Retrieval Defaults' && (
            <>
              <SettingRow label="Default Top-K" value={topK} onChange={setTopK} type="number" help="Number of document chunks retrieved per query" />
              <SettingRow label="Similarity Threshold" value="0.65" onChange={() => {}} type="number" help="Minimum retrieval score to include a chunk" />
              <SettingRow label="Reranking" value="Disabled" onChange={() => {}} type="select" options={['Disabled', 'MMR', 'Cross-encoder']} />
            </>
          )}

          {activeSection === 'Embedding Model' && (
            <>
              <SettingRow label="Embedding Model" value={embeddingModel} onChange={setEmbeddingModel} type="select" options={['text-embedding-ada-002', 'text-embedding-3-small', 'text-embedding-3-large']} />
              <SettingRow label="Embedding Dimensions" value="1536" onChange={() => {}} type="number" />
              <SettingRow label="Batch Size" value="512" onChange={() => {}} type="number" />
            </>
          )}

          {activeSection === 'Parsing' && (
            <>
              <SettingRow label="Chunk Size (tokens)" value={chunkSize} onChange={setChunkSize} type="number" help="Target token count per document chunk" />
              <SettingRow label="Chunk Overlap (tokens)" value={chunkOverlap} onChange={setChunkOverlap} type="number" help="Overlap between consecutive chunks" />
              <SettingRow label="PDF Parser" value="pypdf2" onChange={() => {}} type="select" options={['pypdf2', 'pdfminer', 'pymupdf']} />
              <SettingRow label="DOCX Parser" value="python-docx" onChange={() => {}} type="select" options={['python-docx']} />
            </>
          )}

          {(activeSection === 'API Configuration' || activeSection === 'Workspace') && (
            <div style={{ fontSize: 13, color: '#55535d', lineHeight: 1.6, padding: '20px 0' }}>
              API credentials and workspace configuration are managed through environment variables and the server configuration file.
              Contact your system administrator to update these settings.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SettingRow({
  label, value, onChange, type = 'text', options, help
}: {
  label: string; value: string; onChange: (v: string) => void;
  type?: 'text' | 'number' | 'select'; options?: string[]; help?: string;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 13, color: '#f0ede8', fontWeight: 500 }}>{label}</label>
      {help && <div style={{ fontSize: 11.5, color: '#55535d' }}>{help}</div>}
      {type === 'select' && options ? (
        <select
          value={value}
          onChange={e => onChange(e.target.value)}
          style={{
            background: '#17171d', border: '1px solid #2c2c3a', borderRadius: 5,
            color: '#f0ede8', fontSize: 13, padding: '8px 10px',
            fontFamily: 'inherit', outline: 'none', cursor: 'pointer',
          }}
        >
          {options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : (
        <input
          type={type === 'number' ? 'number' : 'text'}
          value={value}
          onChange={e => onChange(e.target.value)}
          style={{
            background: '#17171d', border: '1px solid #2c2c3a', borderRadius: 5,
            color: '#f0ede8', fontSize: 13, padding: '8px 10px',
            fontFamily: 'inherit', outline: 'none', width: '100%',
          }}
        />
      )}
    </div>
  );
}
