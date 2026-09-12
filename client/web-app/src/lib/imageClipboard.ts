export function imageFileFromClipboard(data: DataTransfer): File | null {
  const itemFile = Array.from(data.items)
    .find((item) => item.kind === 'file' && item.type.startsWith('image/'))
    ?.getAsFile();
  return itemFile || Array.from(data.files).find((file) => file.type.startsWith('image/')) || null;
}
