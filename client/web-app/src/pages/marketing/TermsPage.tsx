import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { MarkdownBody } from '../../components/marketing/MarkdownBody';

// Nội dung pháp lý tĩnh, cố định tiếng Việt — không qua i18n để tránh dịch
// máy làm sai lệch nghĩa. Google crawl trang này để verify OAuth consent
// screen nên phải render server-side-free, không phụ thuộc API/auth.
const TERMS_BODY = `Chào mừng bạn đến với mondaiy ("chúng tôi", "mondaiy", "Dịch vụ"), một ứng dụng hỗ trợ học tập/làm việc giúp người dùng tổng hợp email và nhắc hạn công việc. Bằng việc truy cập hoặc sử dụng mondaiy tại địa chỉ [https://c3-app-004.io.vn](https://c3-app-004.io.vn), bạn đồng ý bị ràng buộc bởi các Điều khoản Sử dụng này. Nếu bạn không đồng ý, vui lòng không sử dụng Dịch vụ.

## 1. Mô tả dịch vụ

mondaiy là ứng dụng dành cho sinh viên/người học và người đi làm trong các chương trình đào tạo, giúp:

- Đọc (chỉ đọc — read-only) email Gmail của người dùng đã đăng nhập, với sự cho phép rõ ràng qua Google OAuth.
- Tự động tổng hợp email thành các bản tóm tắt công việc (work summaries) và nhắc hạn (deadline reminders), kèm trích dẫn nguồn (source citations) từ email gốc.

mondaiy không thay đổi, xóa, hay gửi email thay mặt người dùng. Quyền truy cập Gmail chỉ giới hạn ở mức đọc dữ liệu cần thiết để tạo bản tóm tắt và nhắc việc.

## 2. Điều kiện sử dụng

- Bạn phải từ 18 tuổi trở lên để sử dụng mondaiy.
- Bạn cần có tài khoản Google hợp lệ để đăng nhập và cấp quyền truy cập Gmail (read-only) cho mondaiy.
- Bạn chịu trách nhiệm bảo mật thông tin đăng nhập và mọi hoạt động diễn ra dưới tài khoản của mình.
- Bạn cam kết cung cấp thông tin chính xác và không sử dụng Dịch vụ cho mục đích trái pháp luật.

## 3. Quyền truy cập dữ liệu Google

Việc mondaiy sử dụng và chuyển giao thông tin nhận được từ Google APIs tuân thủ Google API Services User Data Policy, bao gồm các yêu cầu về Limited Use (Sử dụng Giới hạn). Chi tiết về cách chúng tôi thu thập, sử dụng, lưu trữ và bảo vệ dữ liệu được nêu tại [Chính sách Quyền riêng tư](/policy) của chúng tôi — vui lòng đọc kỹ tài liệu đó cùng với Điều khoản này.

Bạn có thể thu hồi quyền truy cập Gmail của mondaiy bất kỳ lúc nào thông qua [trang Quản lý quyền truy cập bên thứ ba của Google](https://myaccount.google.com/permissions).

## 4. Phí dịch vụ

mondaiy hiện được cung cấp hoàn toàn miễn phí. Chúng tôi có thể giới thiệu các gói trả phí hoặc tính năng cao cấp trong tương lai; nếu có, chúng tôi sẽ thông báo trước và cập nhật Điều khoản này cho phù hợp.

## 5. Quyền sở hữu trí tuệ

Toàn bộ mã nguồn, giao diện, logo, và nội dung của mondaiy (không bao gồm dữ liệu email của người dùng) thuộc quyền sở hữu của chúng tôi hoặc bên cấp phép. Bạn không được sao chép, phân phối lại, hoặc khai thác thương mại Dịch vụ mà không có sự cho phép bằng văn bản.

## 6. Trách nhiệm và giới hạn bảo đảm

Dịch vụ được cung cấp "nguyên trạng" (as is), không có bảo đảm dưới bất kỳ hình thức nào, kể cả bảo đảm về tính chính xác của các bản tóm tắt hay nhắc hạn được tạo tự động. mondaiy không chịu trách nhiệm cho các thiệt hại phát sinh từ việc bạn dựa vào nội dung tóm tắt tự động thay vì kiểm tra lại email gốc.

Trong phạm vi pháp luật cho phép, mondaiy không chịu trách nhiệm pháp lý đối với các thiệt hại gián tiếp, ngẫu nhiên, hoặc hệ quả phát sinh từ việc sử dụng hoặc không thể sử dụng Dịch vụ.

## 7. Chấm dứt dịch vụ

Chúng tôi có quyền tạm ngưng hoặc chấm dứt quyền truy cập của bạn vào mondaiy nếu phát hiện vi phạm Điều khoản này. Bạn có thể ngừng sử dụng Dịch vụ và thu hồi quyền truy cập Gmail bất kỳ lúc nào (xem mục 3).

## 8. Thay đổi Điều khoản

Chúng tôi có thể cập nhật Điều khoản Sử dụng này theo thời gian. Phiên bản mới sẽ được đăng tại trang này kèm ngày cập nhật. Việc bạn tiếp tục sử dụng mondaiy sau khi thay đổi có hiệu lực đồng nghĩa với việc bạn chấp nhận các thay đổi đó.

## 9. Luật áp dụng

Điều khoản này được điều chỉnh và giải thích theo pháp luật Việt Nam. Mọi tranh chấp phát sinh sẽ được ưu tiên giải quyết thông qua thương lượng; nếu không đạt được thỏa thuận, tranh chấp sẽ được đưa ra cơ quan có thẩm quyền theo quy định pháp luật Việt Nam.

## 10. Liên hệ

Nếu có câu hỏi về Điều khoản Sử dụng này, vui lòng liên hệ:

Email: [phonginformationtechnology@gmail.com](mailto:phonginformationtechnology@gmail.com)`;

export const TermsPage: React.FC = () => {
  const { t } = useTranslation();

  useEffect(() => {
    document.title = 'Terms of Service - mondaiy';
  }, []);

  return (
    <article className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-500 transition-colors hover:text-action-solid"
      >
        <ArrowLeft className="h-4 w-4" strokeWidth={1.5} />
        {t.marketing.blogBackHome}
      </Link>

      <header className="mt-8 space-y-4">
        <h1 className="text-balance text-[clamp(2rem,4vw,2.85rem)] font-semibold leading-[1.15] tracking-[-0.025em] text-ink-900">
          Điều khoản Sử dụng (Terms of Service) — mondaiy
        </h1>
        <p className="text-sm text-ink-500">Cập nhật lần cuối: 24/08/2026</p>
      </header>

      <MarkdownBody source={TERMS_BODY} className="mt-10 space-y-5 text-base leading-relaxed text-ink-700" />
    </article>
  );
};
