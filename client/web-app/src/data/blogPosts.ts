/**
 * Bài blog marketing — thêm/sửa entry tại đây khi đăng nội dung mới.
 */
export type BlogPost = {
  id: string;
  slug: string;
  title: string;
  titleVi: string;
  excerpt: string;
  excerptVi: string;
  body: string;
  bodyVi: string;
  author: string;
  publishedAt: string;
  tags: string[];
  /** URL ảnh cover (http / local asset / API asset). */
  coverImageUrl?: string | null;
};

export const blogPosts: BlogPost[] = [
  {
    id: 'an-why-mondaiy',
    slug: 'why-we-built-mondaiy',
    title: 'Why we built mondaiy in the first place',
    titleVi: 'Vì sao chúng tôi làm mondaiy',
    excerpt:
      'Too many tabs, endless pings, and the constant fear of missing the one deadline that actually mattered.',
    excerptVi:
      'Quá nhiều ứng dụng, thông báo reo liên tục — nhưng bạn vẫn có thể sót đúng chiếc deadline quan trọng nhất.',
    body: `Most of our day is scattered across Discord servers, project emails, calendars, and learning portals. The real chore isn't reading every message — it's connecting the dots: figuring out which announcement overrides yesterday's chat, and what you actually need to do next.

We built mondaiy to do the heavy reading for you. It checks your connected sources, surfaces what changed, and prepares drafts for your next steps — without taking over your calendar or sending messages behind your back.

If you are juggling competing deadlines across multiple platforms, this was made for you.`,
    bodyVi: `Một ngày học tập và làm việc thường bị xé nhỏ giữa kênh chat Discord, hòm thư, lịch học và cổng portal. Khó khăn lớn nhất không phải là đọc từng mẩu tin, mà là ráp các mảnh thông tin lại với nhau: thông báo mới nào vừa thay kế hoạch cũ, và việc tiếp theo cần làm là gì.

Chúng tôi xây dựng mondaiy để đọc và đối chiếu giúp bạn. Ứng dụng quét các nguồn bạn liên kết, chỉ ra điểm thay đổi và chuẩn bị sẵn bản nháp hành động — không tự ý sửa lịch hay gửi tin ngoài ý muốn.

mondaiy dành cho những ai đang phải gánh nhiều đầu việc cùng lúc.`,
    author: 'Thái Hoài An',
    publishedAt: '2026-08-05',
    tags: ['product'],
  },
  {
    id: 'phong-how-it-fits',
    slug: 'how-mondaiy-fits-together',
    title: 'How the pieces fit together under the hood',
    titleVi: 'Các phần ghép lại với nhau thế nào',
    excerpt:
      'What actually happens behind the scenes after you connect a source feed.',
    excerptVi:
      'Những gì thực sự diễn ra phía sau màn hình sau khi bạn kết nối một nguồn dữ liệu.',
    body: `When you connect an account, mondaiy gets read-only access to recent messages and calendar entries. It compares new updates with what you already know, then flags official changes, open questions, and conflicts between channels.

Every key line in your briefing links back to the original source with a quote and timestamp. When two channels give different deadlines, mondaiy does not guess — it shows both sides and suggests you check with your mentor.

A summary is only useful if you can trace it back to reality in one click.`,
    bodyVi: `Khi bạn liên kết một tài khoản, mondaiy chỉ nhận quyền đọc các tin nhắn và sự kiện gần đây. Hệ thống so sánh thông tin mới với những việc bạn đang theo dõi, lọc ra thông báo chính thức, gom các việc chưa rõ và chỉ ra điểm mâu thuẫn giữa các kênh.

Mọi dòng tóm tắt quan trọng đều kèm link về tin nhắn gốc, trích dẫn và mốc thời gian cụ thể. Khi hai kênh thông báo hai hạn nộp khác nhau, mondaiy không tự đoán — nó hiển thị cả hai bên và đề xuất bạn hỏi lại người phụ trách.

Bản tóm tắt chỉ có giá trị khi bạn kiểm chứng được nguồn gốc chỉ bằng một cú click.`,
    author: 'Nguyễn Văn Phong',
    publishedAt: '2026-08-02',
    tags: ['engineering'],
  },
  {
    id: 'nhi-clear-mornings',
    slug: 'designing-for-a-calmer-morning',
    title: 'Designing for a calmer morning screen',
    titleVi: 'Thiết kế cho buổi sáng bớt rối',
    excerpt:
      'Less focus on looking clever, more focus on showing what matters before you start your day.',
    excerptVi:
      'Bớt phô diễn công nghệ, tập trung hiển thị đúng việc bạn cần biết trước khi bắt đầu ngày mới.',
    body: `We designed the daily briefing to feel like a clean desk, not a dashboard covered in notification badges. You get one main story of what needs attention, clear flags when information is uncertain, and enough breathing room to decide what to do next.

Empty states tell you plainly when nothing needs your attention. Conflict states highlight mismatches without panic. If opening mondaiy makes your morning feel louder or more stressful, we treat that as a design bug.`,
    bodyVi: `Chúng tôi thiết kế bản tin hằng ngày giống như một mặt bàn gọn gàng, chứ không phải dashboard ngập chấm đỏ thông báo. Bạn nhìn thấy mạch việc chính cần xử lý, nhãn rõ khi thông tin chưa chắc chắn, và đủ khoảng lặng để quyết định bước tiếp theo.

Khi không có gì mới, hệ thống nói thẳng là không có việc cần bạn bận tâm. Khi có mâu thuẫn, hệ thống chỉ rõ điểm lệch mà không gây hoang mang. Nếu mở mondaiy mà bạn thấy ồn ào và căng thẳng hơn, đó là lỗi thiết kế của chúng tôi.`,
    author: 'Lê Thị Yến Nhi',
    publishedAt: '2026-07-28',
    tags: ['design'],
  },
  {
    id: 'dung-you-stay-in-control',
    slug: 'you-approve-every-action',
    title: 'You approve every action — on purpose',
    titleVi: 'Mọi hành động đều do bạn duyệt — cố ý như vậy',
    excerpt:
      'mondaiy drafts tasks and calendar suggestions, but nothing saves until you say yes.',
    excerptVi:
      'mondaiy gợi ý tạo task và xếp lịch, nhưng không có gì được lưu nếu bạn chưa bấm đồng ý.',
    body: `mondaiy reads broadly so you do not have to, but it writes strictly after your approval. Every suggested task, calendar block, and reminder comes with a confidence tag — Certain, Possible, or Ask for clarification.

Product quality is not about automating everything silently. It is about eliminating silent mistakes. If a suggested action cannot be traced back to a source, it should never look like a finished decision on your calendar.`,
    bodyVi: `mondaiy đọc rộng để bạn đỡ mất công, nhưng chỉ thực hiện hành động ra ngoài sau khi bạn duyệt. Mọi task gợi ý, khung giờ xếp lịch hay nhắc việc đều đi kèm nhãn độ tin cậy — Chắc chắn, Có thể hoặc Cần hỏi lại.

Chất lượng của một công cụ hỗ trợ không nằm ở việc tự động hóa âm thầm mọi thứ, mà là không tạo ra những sai sót vô hình. Một việc chưa rõ nguồn gốc không được tự biến thành lịch hẹn chính thức của bạn.`,
    author: 'Nguyễn Đức Dũng',
    publishedAt: '2026-07-22',
    tags: ['trust'],
  },
];
