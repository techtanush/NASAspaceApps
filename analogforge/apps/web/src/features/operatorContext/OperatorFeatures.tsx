import { useId } from 'react';
import { Button, FormField, Input } from '../../components/ui';

export interface CustomFeature { name: string; value: string | null; unit: string | null; unknown: boolean }

export function OperatorFeatures({ features, onChange, limit, disabled = false }: {
  features: CustomFeature[]; onChange: (features: CustomFeature[]) => void; limit: number; disabled?: boolean;
}) {
  const id = useId();
  const change = (index: number, patch: Partial<CustomFeature>) => onChange(features.map((feature, position) => position === index ? { ...feature, ...patch } : feature));
  return <section className="operator-features" aria-labelledby={`${id}-heading`}>
    <h3 id={`${id}-heading`}>Custom features</h3>
    <p className="helper">These are informational declarations. Set confirmed mass, slope, clearance, battery and other supported limits in the numeric rover profile. Unsupported benchmarks remain Unknown.</p>
    {features.length === 0 && <p className="helper">No custom features added.</p>}
    {features.map((feature, index) => <fieldset key={index} className="form-stack" disabled={disabled}>
      <legend>Feature {index + 1}</legend>
      <FormField label="Feature name"><Input value={feature.name} onChange={event => change(index, { name: event.target.value })}/></FormField>
      <label className="checkbox-label"><Input type="checkbox" checked={feature.unknown} onChange={event => change(index, { unknown: event.target.checked, value: event.target.checked ? null : '' })}/>Value unknown</label>
      <FormField label="Declared value" hint={feature.unknown ? 'Unknown; no value will be inferred.' : 'Keep the declaration as written; this field does not set a numeric rover limit.'}><Input disabled={feature.unknown} value={feature.value ?? ''} placeholder={feature.unknown ? 'Unknown' : undefined} onChange={event => change(index, { value: event.target.value })}/></FormField>
      <FormField label="Unit (optional)"><Input value={feature.unit ?? ''} onChange={event => change(index, { unit: event.target.value || null })}/></FormField>
      <Button variant="ghost" onClick={() => onChange(features.filter((_, position) => position !== index))}>Remove feature {index + 1}</Button>
    </fieldset>)}
    <Button disabled={disabled || features.length >= limit} disabledReason={`This context supports at most ${limit} custom features.`} onClick={() => onChange([...features, { name: '', value: null, unit: null, unknown: true }])}>Add custom feature</Button>
  </section>;
}
