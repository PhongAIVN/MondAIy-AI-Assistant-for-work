/** Ảnh đại diện thật của user (Google OAuth avatar_url, xem TokenResponse ở
 * src/models/schemas.py) — chưa đăng nhập qua Google hoặc chưa refresh lần
 * nào thì avatarUrl null, dùng mascot làm ảnh dự phòng thay vì để trống.
 * Dùng chung ở header sidepanel lẫn options page. */
export function HeaderAvatar({ avatarUrl }: { avatarUrl: string | null | undefined }) {
  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt="Ảnh đại diện"
        width={26}
        height={26}
        referrerPolicy="no-referrer"
        className="h-[26px] w-[26px] shrink-0 rounded-full border border-border object-cover"
      />
    );
  }
  return (
    <img
      src="/mondaiy-mascot.png"
      alt=""
      width={26}
      height={26}
      className="h-[26px] w-[26px] shrink-0 rounded-full border border-border bg-surface object-contain p-0.5"
    />
  );
}
