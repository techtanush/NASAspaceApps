import { MotionConfig, motion } from 'motion/react';

/** Presentation changes disclosure depth, never the underlying evidence or its status. */
export function ResultPresentation({ technical, onChange }: { technical: boolean; onChange: (technical: boolean) => void }) {
  return <MotionConfig reducedMotion="user"><div className="mc-result-presentation" role="group" aria-label="Result presentation">
    {[{ label: 'Simplified', value: false }, { label: 'Technical details', value: true }].map(option => <button key={option.label} type="button" aria-pressed={technical === option.value} onClick={() => onChange(option.value)}>
      {technical === option.value && <motion.span className="mc-presentation-indicator" layoutId="result-presentation" transition={{ duration: .18 }} aria-hidden="true"/>}
      <span>{option.label}</span>
    </button>)}
  </div></MotionConfig>;
}
