/// Pul summasini «450 000» ko'rinishida (probel bilan) formatlaydi.
String dsSom(num value, {bool withSuffix = false, bool sign = false}) {
  final negative = value < 0;
  final digits = value.abs().round().toString();
  final buf = StringBuffer();
  for (var i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 == 0) buf.write(' ');
    buf.write(digits[i]);
  }
  var out = buf.toString();
  if (sign) {
    out = negative ? '−$out' : '+$out';
  } else if (negative) {
    out = '−$out';
  }
  if (withSuffix) out = '$out so\'m';
  return out;
}
