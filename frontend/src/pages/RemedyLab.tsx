import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, type BrewDeviceResult, type DeviceCell, type InstallDeviceResult, type RemedyCard, type RemedyLab as RemedyLabData } from '../api/endpoints';
import { mediaUrl } from '../api/media';
import LocationMap from '../components/LocationMap';
import StitchReportForm from '../components/StitchReportForm';
import Toast from '../components/Toast';

const DICE_FACE = ['', '⚀', '⚁', '⚂', '⚃', '⚄', '⚅'];

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 14 }}
      onClick={onClose}
    >
      <div
        className="fm-card"
        style={{ maxWidth: 520, width: '100%', maxHeight: '86vh', overflowY: 'auto', margin: 0 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, gap: 8 }}>
          <strong>{title}</strong>
          <button className="fm-btn fm-btn-xs" onClick={onClose} aria-label="Закрыть">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function RemedyLabPage() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [lab, setLab] = useState<RemedyLabData | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [deviceModal, setDeviceModal] = useState<DeviceCell | null>(null);
  const [installResult, setInstallResult] = useState<InstallDeviceResult | null>(null);
  const [showCards, setShowCards] = useState(false);
  const [showStock, setShowStock] = useState(false);
  const [brewResult, setBrewResult] = useState<BrewDeviceResult | null>(null);

  const fieldId = Number(id);

  const load = useCallback(() => {
    if (!Number.isFinite(fieldId)) return;
    setLoading(true);
    api.remedyLab(fieldId)
      .then(setLab)
      .catch((e) => setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка')))
      .finally(() => setLoading(false));
  }, [fieldId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(null), 4000);
    return () => clearTimeout(t);
  }, [msg]);

  async function doInstall(cell: DeviceCell) {
    setBusy(true); setMsg(null);
    try {
      const res = await api.installRemedyDevice(cell.id);
      setInstallResult(res);
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  async function doBrew(card: RemedyCard) {
    if (!lab) return;
    const cell = (lab.device_cells ?? []).find(
      (c) => c.device?.build_status === 'built' && c.remedies.some((r) => r.remedy_id === card.remedy_id),
    );
    if (!cell) {
      setMsg('✗ Нет установленного прибора для этого лекарства');
      return;
    }
    setBusy(true); setMsg(null);
    try {
      const res = await api.brewRemedy(card.id, cell.id);
      setBrewResult(res);
      setDeviceModal(null);
      await load();
    } catch (e: any) {
      setMsg('✗ ' + (e?.response?.data?.detail || 'Ошибка'));
    } finally { setBusy(false); }
  }

  if (loading && !lab) {
    return (
      <div style={{ maxWidth: 'var(--shell-max-width)', margin: '0 auto', padding: 'var(--shell-pad)' }}>
        <div className="fm-card">Загрузка Лесной аптеки…</div>
      </div>
    );
  }

  const cells = lab?.device_cells ?? [];
  const stock = lab?.remedies_stock ?? [];
  const cards = lab?.remedy_cards ?? [];

  return (
    <>
      <LocationMap mapUrl={lab?.map_url ?? null} name={lab?.name ?? ''} emoji="⚗️" onBack={() => nav('/infirmary')} backLabel="Лечебница">
        {lab && cells.length > 0 && (
          <div
            style={{
              position: 'absolute', inset: 0, display: 'grid',
              gridTemplateColumns: `repeat(${lab.cols}, 1fr)`,
              gridTemplateRows: `repeat(${lab.rows}, 1fr)`,
            }}
          >
            {cells.map((cell) => {
              const dev = cell.device;
              const brewing = dev != null && dev.brew_card_id != null;
              return (
                <div
                  key={`dev-${cell.id}`}
                  onClick={() => { setInstallResult(null); setDeviceModal(cell); }}
                  style={{
                    gridColumn: `${cell.col + 1} / span 1`,
                    gridRow: `${cell.row + 1} / span 1`,
                    position: 'relative', display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center',
                    borderRadius: 6, overflow: 'hidden', padding: 2,
                    border: brewing
                      ? '2px solid rgba(120,220,140,0.75)'
                      : dev?.build_status === 'built'
                        ? '1px solid rgba(160,120,220,0.65)'
                        : '2px dashed rgba(160,120,220,0.55)',
                    background: brewing ? 'rgba(111,174,74,0.22)' : 'rgba(30,20,50,0.30)',
                    cursor: 'pointer', touchAction: 'manipulation',
                  }}
                >
                  {!dev && (
                    <div style={{ fontSize: 'clamp(12px,3vw,20px)', color: '#e6d9ff', textAlign: 'center', lineHeight: 1.2, textShadow: '0 1px 3px #000', fontWeight: 600 }}>
                      🔧<div style={{ fontSize: 9 }}>прибор</div>
                    </div>
                  )}
                  {dev?.build_status === 'building' && (
                    <div style={{ fontSize: 'clamp(10px,2.4vw,14px)', color: '#ffd9a0', textAlign: 'center', lineHeight: 1.2, textShadow: '0 1px 3px #000', fontWeight: 600 }}>
                      🛠 {dev.accumulated}/{dev.required}
                    </div>
                  )}
                  {dev?.build_status === 'built' && !brewing && (
                    <div style={{ fontSize: 'clamp(12px,3vw,20px)', lineHeight: 1 }}>⚗️</div>
                  )}
                  {brewing && dev && (
                    <div style={{ textAlign: 'center', lineHeight: 1.15 }}>
                      <div style={{ fontSize: 'clamp(12px,3vw,20px)' }}>{dev.brew_dice.map((d) => DICE_FACE[d] || '⚀').join('')}</div>
                      <div style={{ fontSize: 'clamp(8px,2vw,11px)', color: '#b8ffb8', fontWeight: 700, textShadow: '0 1px 2px #000' }}>
                        {dev.brew_accumulated}/{dev.brew_required}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </LocationMap>

      <div style={{ position: 'fixed', left: 12, right: 76, bottom: 'calc(12px + var(--vk-inset-bottom, 0px))', zIndex: 30, display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
        <button className="fm-btn" onClick={() => setShowCards(true)}>📋 Рецепты ({cards.length})</button>
        <button className="fm-btn fm-btn-outline" onClick={() => setShowStock(true)}>💊 Лекарства ({stock.reduce((a, s) => a + s.qty, 0)})</button>
      </div>

      {msg && <Toast text={msg} onClose={() => setMsg(null)} />}

      {deviceModal && !brewResult && (
        <Modal title="🔧 Прибор" onClose={() => { setDeviceModal(null); setInstallResult(null); }}>
          {!deviceModal.device && !installResult && (
            <>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '0 0 10px' }}>
                Свободная клетка прибора. Здесь можно производить:
              </p>
              <div style={{ fontSize: 13, marginBottom: 10 }}>
                {deviceModal.remedies.length === 0
                  ? <span style={{ color: 'var(--text-muted)' }}>Админ не привязал лекарства к этому прибору.</span>
                  : deviceModal.remedies.map((r) => <span key={r.remedy_id} className="fm-chip" style={{ margin: 2 }}>{r.remedy_name}</span>)}
              </div>
              <button className="fm-btn" style={{ width: '100%' }} disabled={busy} onClick={() => doInstall(deviceModal)}>
                🔧 Установить прибор ({deviceModal.install_cards} карт)
              </button>
            </>
          )}

          {installResult && (
            <>
              <p style={{ fontSize: 14, margin: '0 0 8px' }}>
                Норма установки прибора: <strong>{installResult.required} ❆</strong>
              </p>
              <div style={{ display: 'flex', justifyContent: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                {installResult.cards.map((c, i) => (
                  <span key={i} className="fm-chip">
                    {c.is_treasure ? '💎' : c.color === 'green' ? '🟢' : c.color === 'blue' ? '🔵' : '🟣'} ×{c.value}
                  </span>
                ))}
              </div>
              <StitchReportForm
                contextType="remedy_device_install"
                contextId={deviceModal.id}
                required={installResult.required}
                busy={busy}
                onDone={async () => { setMsg('✓ Прибор установлен!'); setDeviceModal(null); setInstallResult(null); await load(); }}
              />
            </>
          )}

          {deviceModal.device?.build_status === 'building' && !installResult && (
            <>
              <p style={{ fontSize: 14, margin: '0 0 8px' }}>
                Установка: <strong>{deviceModal.device.accumulated}/{deviceModal.device.required} ❆</strong>
              </p>
              <StitchReportForm
                contextType="remedy_device_install"
                contextId={deviceModal.id}
                required={deviceModal.device.required}
                busy={busy}
                onDone={async () => { setMsg('✓ Прибор установлен!'); setDeviceModal(null); await load(); }}
              />
            </>
          )}

          {deviceModal.device?.build_status === 'built' && deviceModal.device.brew_card_id == null && (
            <div className="fm-card" style={{ fontSize: 13 }}>
              ⚗️ Прибор готов. Выберите рецепт (кнопка «📋 Рецепты») и сварите лекарство здесь.
              {deviceModal.remedies.length > 0 && (
                <div style={{ marginTop: 6 }}>
                  Производит: {deviceModal.remedies.map((r) => r.remedy_name).join(', ')}
                </div>
              )}
            </div>
          )}

          {deviceModal.device?.brew_card_id != null && deviceModal.device && (
            <>
              <p style={{ fontSize: 14, margin: '0 0 6px' }}>
                🎲 {deviceModal.device.brew_dice.map((d) => DICE_FACE[d] || '⚀').join(' ')} → норма{' '}
                <strong>{deviceModal.device.brew_required} ❆</strong>
              </p>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '0 0 8px' }}>
                Варится: «{deviceModal.device.brew_remedy_name}» для {deviceModal.device.brew_patient_name}.
                Отшито: {deviceModal.device.brew_accumulated}/{deviceModal.device.brew_required}.
              </p>
              <StitchReportForm
                contextType="remedy_brew"
                contextId={deviceModal.device.id}
                required={deviceModal.device.brew_required ?? 0}
                busy={busy}
                onDone={async () => { setMsg('✓ Лекарство готово! Оно на складе аптеки.'); setDeviceModal(null); await load(); }}
              />
            </>
          )}
        </Modal>
      )}

      {brewResult && (
        <Modal title={`⚗️ Варка: ${brewResult.remedy_name}`} onClose={() => setBrewResult(null)}>
          <p style={{ fontSize: 16, textAlign: 'center', margin: '0 0 8px' }}>
            🎲 {brewResult.dice.map((d) => DICE_FACE[d] || '⚀').join(' ')} → норма{' '}
            <strong>{brewResult.required} ❆</strong>
          </p>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '0 0 8px' }}>
            Лекарство «{brewResult.remedy_name}» для {brewResult.patient_name}. Отшейте норму — и оно появится на складе.
          </p>
          <StitchReportForm
            contextType="remedy_brew"
            contextId={brewResult.device.id}
            required={brewResult.required}
            busy={busy}
            onDone={async () => { setMsg('✓ Лекарство готово! Оно на складе аптеки.'); setBrewResult(null); await load(); }}
          />
        </Modal>
      )}

      {showCards && (
        <Modal title={`📋 Актуальные рецепты (${cards.length})`} onClose={() => setShowCards(false)}>
          {cards.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Актуальных рецептов нет — поставьте диагнозы в лечебнице.</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
              {cards.map((card) => {
                const ready = card.recipe_items.every((i) => i.have >= i.qty);
                return (
                  <div key={card.id} className="fm-card fm-rise" style={{ fontSize: 13 }}>
                    <strong>{card.patient_name}</strong>
                    <div style={{ color: 'var(--text-muted)', margin: '4px 0' }}>{card.remedy_name}</div>
                    {card.recipe_items.map((i, idx) => (
                      <div key={idx} style={{ fontSize: 12, color: i.have >= i.qty ? 'var(--success)' : 'var(--danger, #e08080)' }}>
                        {i.ingredient_name || i.plant_name}: {i.have}/{i.qty}
                      </div>
                    ))}
                    <button
                      className="fm-btn fm-btn-sm fm-btn-wrap"
                      style={{ width: '100%', marginTop: 8 }}
                      disabled={busy || !ready}
                      onClick={() => { setShowCards(false); doBrew(card); }}
                    >
                      ⚗️ Сварить (2 кубика)
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </Modal>
      )}

      {showStock && (
        <Modal title="💊 Склад аптеки" onClose={() => setShowStock(false)}>
          {stock.length === 0 ? (
            <div className="fm-card" style={{ color: 'var(--text-muted)' }}>Лекарств пока нет.</div>
          ) : (
            <div className="fm-grid">
              {stock.map((s) => (
                <div key={s.remedy_id} className="fm-card fm-rise" style={{ textAlign: 'center', fontSize: 13 }}>
                  {s.remedy_image_url && (
                    <img src={mediaUrl(s.remedy_image_url)} alt="" style={{ height: 56, maxWidth: '100%', objectFit: 'contain' }} />
                  )}
                  <strong style={{ display: 'block' }}>{s.remedy_name}</strong>
                  <span className="fm-chip">×{s.qty}</span>
                </div>
              ))}
            </div>
          )}
          {(lab?.apothecary ?? []).length > 0 && (
            <>
              <div style={{ borderTop: '1px solid var(--border)', margin: '12px 0 8px' }} />
              <strong style={{ fontSize: 13 }}>🍃 Ингредиенты</strong>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                {(lab?.apothecary ?? []).map((a) => (
                  <span key={a.ingredient_id} className="fm-chip">{a.image_url ? <img src={mediaUrl(a.image_url)} alt="" style={{ width: 16, height: 16, objectFit: 'contain', verticalAlign: '-3px' }} /> : '🍃'} {a.name} ×{a.qty}</span>
                ))}
              </div>
            </>
          )}
        </Modal>
      )}
    </>
  );
}
