/**
 * Intent cho quick actions (task / calendar / mentor) trên câu trả lời AI.
 * Chat thường không hiện nút — chỉ khi user hỏi lên kế hoạch hoặc tóm tắt ngày.
 */

export function isPlanningOrSummaryIntent(input: string): boolean {
  const text = input.normalize('NFKC').toLowerCase().trim();
  if (!text) return false;

  const planning =
    /(lên\s*kế\s*hoạch|ke\s*hoach|giúp\s*(tôi\s*)?(lên\s*)?kế\s*hoạch|lập\s*kế\s*hoạch|lên\s*plan|help\s+me\s+plan|make\s+(me\s+)?a\s+plan|create\s+a\s+plan|plan\s+(my|for|the)\b|planning\s+help)/.test(
      text,
    );

  const daySummary =
    /(tóm\s*tắt\s*(ngày|hôm)|tong\s*ket\s*ngày|tổng\s*kết\s*(ngày|hôm)|(hôm\s*qua|hôm\s*nay|hôm\s*kia).{0,40}(đã\s*)?(làm\s*gì|làm\s*những\s*gì|làm\s*việc\s*gì)|(làm\s*gì|làm\s*những\s*gì).{0,20}(hôm\s*qua|hôm\s*nay)|summariz(e|ing)\s+(.{0,40}\s)?(my\s+)?(day|today|yesterday)|what\s+(did\s+i\s+do|i\s+did)\s+(today|yesterday)|daily\s+summary|recap\s+(today|yesterday|my\s+day)|end[\s-]?of[\s-]?day\s+(summary|recap))/.test(
      text,
    );

  return planning || daySummary;
}

export type PlanningSummaryMockReply = {
  text: string;
  summary: string;
  whatChanged: string;
  whyItMatters: string;
  recommendedNextStep: string;
  confidence: 'certain';
};

/** Bản trả lời mock khi user hỏi lên kế hoạch / tóm tắt ngày (kèm quick actions). */
export function buildPlanningOrSummaryMockReply(
  question: string,
  language: 'en' | 'vi' = 'en',
): PlanningSummaryMockReply {
  const text = question.normalize('NFKC').toLowerCase();
  const isPlanning =
    /(lên\s*kế\s*hoạch|ke\s*hoach|lập\s*kế\s*hoạch|help\s+me\s+plan|make\s+(me\s+)?a\s+plan|create\s+a\s+plan|plan\s+(my|for|the)\b|planning\s+help)/.test(
      text,
    );

  if (isPlanning) {
    if (language === 'vi') {
      return {
        text: [
          'Dựa trên các nguồn đã kết nối, đây là bản nháp kế hoạch gợi ý (mock):',
          '',
          '1. **Ưu tiên hôm nay** — chốt deliverable đang gần hạn nhất trên Canvas.',
          '2. **Khối lịch** — dành 90 phút tập trung + 15 phút buffer trước deadline.',
          '3. **Hỏi mentor** — làm rõ điểm còn mâu thuẫn giữa Discord và thông báo chính thức.',
          '',
          'Bạn có thể dùng các nút bên dưới để tạo bản nháp task, gợi ý lịch, hoặc soạn câu hỏi mentor.',
        ].join('\n'),
        summary:
          'Kế hoạch mock gồm 3 bước: ưu tiên deliverable gần hạn, đặt khối lịch làm việc, và hỏi mentor nếu còn mâu thuẫn nguồn.',
        whatChanged: 'Các cập nhật gần đây về hạn nộp và lịch mentor được gom thành một kế hoạch hành động.',
        whyItMatters: 'Giúp bạn chuyển từ “đọc tin” sang việc có thể xác nhận ngay trên task/calendar.',
        recommendedNextStep:
          'Chọn “Tạo bản nháp nhiệm vụ” hoặc “Đặt lịch chương trình” để xem bản nháp trước khi xác nhận.',
        confidence: 'certain',
      };
    }
    return {
      text: [
        'Based on your connected sources, here is a mock planning draft:',
        '',
        '1. **Today’s priority** — finish the nearest Canvas deliverable first.',
        '2. **Calendar block** — reserve 90 focused minutes plus a 15-minute buffer before the deadline.',
        '3. **Mentor question** — clarify any Discord vs official announcement mismatch.',
        '',
        'Use the buttons below to prepare a task draft, suggest a calendar block, or draft a mentor question.',
      ].join('\n'),
      summary:
        'Mock plan with three steps: prioritize the nearest deliverable, reserve focus time, and ask your mentor about source conflicts.',
      whatChanged: 'Recent deadline and mentor-schedule updates were rolled into one action plan.',
      whyItMatters: 'Moves you from reading updates to confirmable next actions on tasks and calendar.',
      recommendedNextStep:
        'Choose “Prepare task draft” or “Suggest Calendar block” to review a draft before confirming.',
      confidence: 'certain',
    };
  }

  if (language === 'vi') {
    return {
      text: [
        'Đây là bản tóm tắt ngày mẫu (mock) từ các nguồn đã kết nối:',
        '',
        '- **Đã làm / đã thấy:** có cập nhật hạn nộp và thông báo mentor trên Canvas/Discord.',
        '- **Còn mở:** 1–2 việc cần xác nhận trước khi hết hạn.',
        '- **Gợi ý tiếp theo:** chuyển thành task hoặc khối lịch để không sót việc.',
        '',
        'Dùng các nút bên dưới nếu bạn muốn tạo nháp hành động ngay.',
      ].join('\n'),
      summary:
        'Tóm tắt mock: có cập nhật hạn nộp/mentor trong ngày; còn vài việc mở cần chốt trước deadline.',
      whatChanged: 'Ngày làm việc được gom thành các điểm đã thấy và việc còn mở.',
      whyItMatters: 'Giúp bạn nhìn nhanh tiến độ thay vì đọc lại từng nguồn.',
      recommendedNextStep: 'Dùng “Tạo bản nháp nhiệm vụ” để biến việc còn mở thành task có thể duyệt.',
      confidence: 'certain',
    };
  }

  return {
    text: [
      'Here is a mock day summary from your connected sources:',
      '',
      '- **Seen today:** deadline and mentor updates across Canvas/Discord.',
      '- **Still open:** one or two items to confirm before the deadline.',
      '- **Next:** turn them into a task or calendar block so nothing slips.',
      '',
      'Use the buttons below if you want to draft an action now.',
    ].join('\n'),
    summary:
      'Mock day summary: deadline/mentor updates appeared; a few open items still need confirmation.',
    whatChanged: 'The day was rolled up into what you already saw and what remains open.',
    whyItMatters: 'Gives a fast progress view instead of re-reading every source.',
    recommendedNextStep: 'Use “Prepare task draft” to turn open items into a reviewable task.',
    confidence: 'certain',
  };
}

/** Lấy câu user ngay trước một tin AI để quyết định hiện quick actions. */
export function shouldShowMessageQuickActions(
  messages: ReadonlyArray<{ sender: string; text: string }>,
  aiMessageIndex: number,
): boolean {
  for (let i = aiMessageIndex - 1; i >= 0; i -= 1) {
    if (messages[i]?.sender === 'user') {
      return isPlanningOrSummaryIntent(messages[i].text);
    }
  }
  return false;
}
