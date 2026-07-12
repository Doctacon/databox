const visibleLabelCollator = new Intl.Collator("en", { sensitivity: "base", numeric: true });

export function compareVisibleLabels(
  leftLabel: string,
  rightLabel: string,
  leftTie = "",
  rightTie = "",
): number {
  return visibleLabelCollator.compare(leftLabel, rightLabel)
    || visibleLabelCollator.compare(leftTie, rightTie);
}
