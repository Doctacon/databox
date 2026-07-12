import { KeyboardEvent, useEffect, useId, useState } from "react";
import { searchLocations } from "./api";
import type { LocationSelection, LocationSuggestion } from "./types";

interface LocationComboboxProps {
  inputId?: string;
  value: string;
  selected: LocationSelection | null;
  disabled: boolean;
  allowFreeText?: boolean;
  onChange: (value: string) => void;
  onSelect: (location: LocationSuggestion) => void;
}

const COORDINATE_PAIR = /^\s*[+-]?\d+(?:\.\d+)?\s*,\s*[+-]?\d+(?:\.\d+)?\s*$/;

export default function LocationCombobox({
  inputId = "location",
  value,
  selected,
  disabled,
  allowFreeText = false,
  onChange,
  onSelect,
}: LocationComboboxProps) {
  const generatedId = useId();
  const listboxId = `${generatedId}-listbox`;
  const helpId = `${generatedId}-help`;
  const statusId = `${generatedId}-status`;
  const [options, setOptions] = useState<LocationSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    const query = value.trim();
    if (
      disabled ||
      query.length < 3 ||
      COORDINATE_PAIR.test(query) ||
      selected?.display_name === query
    ) {
      setOptions([]);
      setOpen(false);
      setActiveIndex(-1);
      setStatus(null);
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setStatus("Searching Arizona places…");
      searchLocations(query, controller.signal)
        .then((rows) => {
          if (controller.signal.aborted) return;
          setOptions(rows);
          setOpen(rows.length > 0);
          setActiveIndex(-1);
          setStatus(rows.length > 0 ? null : "No matching Arizona places found.");
        })
        .catch((reason: unknown) => {
          if (controller.signal.aborted) return;
          setOptions([]);
          setOpen(false);
          setActiveIndex(-1);
          setStatus(
            reason instanceof Error
              ? reason.message
              : "Location search is unavailable; enter Arizona coordinates.",
          );
        });
    }, 250);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [disabled, selected, value]);

  function choose(location: LocationSuggestion) {
    onSelect(location);
    setOptions([]);
    setOpen(false);
    setActiveIndex(-1);
    setStatus(null);
  }

  function keyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      setOpen(false);
      setActiveIndex(-1);
      return;
    }
    if (!open || options.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => (current + 1) % options.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => (current <= 0 ? options.length - 1 : current - 1));
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      choose(options[activeIndex]);
    }
  }

  return (
    <div className="location-combobox">
      <input
        id={inputId}
        name={inputId}
        role="combobox"
        aria-autocomplete="list"
        aria-controls={listboxId}
        aria-expanded={open}
        aria-activedescendant={activeIndex >= 0 ? `${listboxId}-${activeIndex}` : undefined}
        aria-describedby={`${helpId} ${statusId}`}
        autoComplete="off"
        required={!allowFreeText}
        maxLength={300}
        placeholder="Prescott, Arizona or 34.54,-112.47"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={keyDown}
        onFocus={() => setOpen(options.length > 0)}
        onBlur={() => window.setTimeout(() => setOpen(false), 0)}
      />
      {open && (
        <ul id={listboxId} role="listbox" className="location-options">
          {options.map((option, index) => (
            <li
              id={`${listboxId}-${index}`}
              role="option"
              aria-selected={index === activeIndex}
              className={index === activeIndex ? "active" : undefined}
              key={`${option.display_name}-${option.latitude}-${option.longitude}`}
              onMouseDown={(event) => {
                event.preventDefault();
                choose(option);
              }}
            >
              <strong>{option.display_name}</strong>
              <small>{option.place_type} · {option.latitude.toFixed(4)}, {option.longitude.toFixed(4)}</small>
            </li>
          ))}
        </ul>
      )}
      <small id={helpId}>{allowFreeText
        ? "Select an Arizona place or keep your private text as entered."
        : "Arizona places only. Coordinates must include a negative longitude."}</small>
      <small id={statusId} className="location-status" aria-live="polite">{status}</small>
    </div>
  );
}
