interface Option<T extends string> {
  value: T;
  label: string;
}

interface SegmentedProps<T extends string> {
  label: string;
  options: Option<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}

export function Segmented<T extends string>({ label, options, value, onChange, className = "" }: SegmentedProps<T>) {
  return (
    <div className="field">
      <label>{label}</label>
      <div className={`segmented ${className}`}>
        {options.map((option) => (
          <button
            key={option.value}
            className={`segment${value === option.value ? " active" : ""}`}
            type="button"
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
