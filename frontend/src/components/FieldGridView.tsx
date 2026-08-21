import { useState } from 'react';
import type { FieldDetail } from '../api/endpoints';
import { mediaUrl } from '../api/media';

export default function FieldGridView({ field, playerVkId, onResetNorm, onDeletePlot }: {
  field: FieldDetail;
  playerVkId?: number;
  onResetNorm?: (plotId: number) => void;
  onDeletePlot?: (plotId: number) => void;
}) {
  const [selectedCell, setSelectedCell] = useState<{ col: number; row: number; plotId: number } | null>(null);
  const grid = (() => {
    const g: (FieldDetail['cells'][number] | null)[][] = [];
    for (let r = 0; r < field.rows; r++) {
      const row: (FieldDetail['cells'][number] | null)[] = [];
      for (let c = 0; c < field.cols; c++) {
        row.push(field.cells.find((x) => x.col === c && x.row === r) ?? null);
      }
      g.push(row);
    }
    return g;
  })();

  const KIND_FILL: Record<string, string> = {
    empty: 'transparent',
    tent: 'rgba(224,168,62,0.15)',
    pet: 'rgba(200,130,220,0.15)',
    barnyard: 'rgba(220,180,120,0.15)',
  };

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ position: 'relative', width: '100%', maxWidth: 'min(800px, 100%)', aspectRatio: `${field.cols}/${field.rows}` }}>
        {field.map_url && (
          <img src={mediaUrl(field.map_url)} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', borderRadius: 4 }} />
        )}
        <div style={{ position: 'absolute', inset: 0, display: 'grid', gridTemplateColumns: `repeat(${field.cols}, 1fr)`, gridTemplateRows: `repeat(${field.rows}, 1fr)` }}>
          {grid.flatMap((row, ri) =>
            row.map((cell, ci) => {
              const key = `${ri}-${ci}`;
              const fill = KIND_FILL[cell?.kind || 'empty'] || 'transparent';
              return (
                <div
                  key={key}
                  onClick={() => {
                    if (cell?.plot?.id && playerVkId) {
                      setSelectedCell({ col: ci, row: ri, plotId: cell.plot.id });
                    }
                  }}
                  title={cell?.plot ? `Норма: ${cell.plot.required}❆ · накоплено ${cell.plot.accumulated}/${cell.plot.required}` : undefined}
                  style={{
                    border: `1px solid ${field.grid_color || 'rgba(255,255,255,0.08)'}`,
                    background: fill,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden',
                    position: 'relative',
                    cursor: cell?.plot && playerVkId ? 'pointer' : 'default',
                  }}
                >
                  {cell?.kind === 'bed' && cell.occupant_user_id != null && cell.plant_image_grown && cell.plot?.status === 'grown' && (
                    <img src={mediaUrl(cell.plant_image_grown)} alt="" style={{ width: '85%', height: '85%', objectFit: 'contain', opacity: 0.9 }} />
                  )}
                  {cell?.kind === 'bed' && cell.occupant_user_id != null && cell.plant_image_young && cell.plot?.status === 'planted' && (
                    <img src={mediaUrl(cell.plant_image_young)} alt="" style={{ width: '60%', height: '60%', objectFit: 'contain', opacity: 0.7 }} />
                  )}
                  {cell?.kind === 'pet' && (
                    <div style={{ fontSize: '3vw', opacity: 0.5 }}>🐾</div>
                  )}
                  {cell?.kind === 'barnyard' && (
                    <div style={{ fontSize: '3vw', opacity: 0.5 }}>🐄</div>
                  )}
                </div>
              );
            })
          )}
        </div>
        {field.tents?.map((t) => {
          const spanCols = t.col2 - t.col1 + 1;
          const spanRows = t.row2 - t.row1 + 1;
          return (
            <div key={`tent-${t.id}`} style={{ position: 'absolute', inset: 0, pointerEvents: 'none', display: 'grid', gridTemplateColumns: `repeat(${field.cols}, 1fr)`, gridTemplateRows: `repeat(${field.rows}, 1fr)` }}>
              <div style={{ gridColumn: `${t.col1 + 1} / span ${spanCols}`, gridRow: `${t.row1 + 1} / span ${spanRows}`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4, padding: 6, borderRadius: 6, background: 'rgba(224,168,62,0.12)', overflow: 'hidden' }}>
                {t.image_url && (
                  <img src={mediaUrl(t.image_url)} alt="" style={{ maxWidth: '80%', maxHeight: '50%', objectFit: 'contain' }} />
                )}
                <div style={{ fontSize: 'clamp(10px,2.2vw,14px)', color: '#ffe9b0', textAlign: 'center', textShadow: '0 1px 3px #000', lineHeight: 1.15, fontWeight: 600 }}>
                  ⛺ {t.name}
                </div>
                {t.build_status === 'planted' && (
                  <div style={{ fontSize: 10, color: '#ffd98a' }}>{t.accumulated}/{t.required}</div>
                )}
                {t.build_status === 'slot' && (
                  <div style={{ fontSize: 10, color: '#ccc' }}>слот</div>
                )}
              </div>
            </div>
          );
        })}
        {(field.pet_zones ?? []).map((z) => {
          const spanCols = z.col2 - z.col1 + 1;
          const spanRows = z.row2 - z.row1 + 1;
          const hasPet = z.pet_id != null;
          return (
            <div key={`petzone-${z.id}`} style={{ position: 'absolute', inset: 0, pointerEvents: 'none', display: 'grid', gridTemplateColumns: `repeat(${field.cols}, 1fr)`, gridTemplateRows: `repeat(${field.rows}, 1fr)` }}>
              <div style={{
                gridColumn: `${z.col1 + 1} / span ${spanCols}`,
                gridRow: `${z.row1 + 1} / span ${spanRows}`,
                position: 'relative', overflow: 'hidden',
                border: hasPet ? 'none' : '2px dashed rgba(200,130,220,0.75)',
                borderRadius: 6,
                background: hasPet ? 'transparent' : 'rgba(200,130,220,0.12)',
              }}>
                {hasPet && z.pet_image_url && (
                  <img src={mediaUrl(z.pet_image_url)} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain', pointerEvents: 'none' }} />
                )}
                {hasPet && z.pet_name && (
                  <div style={{ position: 'absolute', left: 2, right: 2, bottom: 1, fontSize: 'clamp(9px,2.2vw,13px)', color: '#e6d9ff', textAlign: 'center', fontWeight: 600, background: 'rgba(10,16,8,0.5)', borderRadius: 4, padding: '0 4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {z.pet_name}
                  </div>
                )}
                {!hasPet && (
                  <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 'clamp(14px,3vw,28px)', lineHeight: 1, pointerEvents: 'none', opacity: 0.85 }}>
                    🐾
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {selectedCell && playerVkId && (
        <div onClick={() => setSelectedCell(null)} style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10, borderRadius: 4 }}>
          <div className="fm-card" onClick={(e) => e.stopPropagation()} style={{ padding: 12, fontSize: 13, textAlign: 'center', minWidth: 160 }}>
            <div style={{ marginBottom: 8, color: 'var(--text-secondary)' }}>
              Клетка ({selectedCell.col}, {selectedCell.row})
            </div>
            <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
              <button type="button" className="fm-btn fm-btn-sm" style={{ background: '#c90', borderColor: '#c90' }}
                onClick={() => { onResetNorm?.(selectedCell.plotId); setSelectedCell(null); }}>
                🎲 Сброс нормы
              </button>
              <button type="button" className="fm-btn fm-btn-sm fm-btn-danger"
                onClick={() => { onDeletePlot?.(selectedCell.plotId); setSelectedCell(null); }}>
                🗑 Удалить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
