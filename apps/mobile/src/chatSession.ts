import {
  createConversation,
  sendConversationMessage,
  type ConversationSendReply,
} from './api/client.ts';

export type SendConversationTurnInput = {
  conversationId: number | null;
  message: string;
  token: string;
  imageData?: string | null;
};

export type SentConversationTurn = {
  conversationId: number;
  createdConversationId: number | null;
  reply: ConversationSendReply;
};

/** Giữ lượt gửi đầu tiên trong cùng một transaction UI, tránh remount giữa chừng. */
export async function sendConversationTurn({
  conversationId,
  message,
  token,
  imageData,
}: SendConversationTurnInput): Promise<SentConversationTurn> {
  let resolvedConversationId = conversationId;
  let createdConversationId: number | null = null;

  if (resolvedConversationId === null) {
    const conversation = await createConversation(message.slice(0, 56), token);
    resolvedConversationId = conversation.id;
    createdConversationId = conversation.id;
  }

  const reply = await sendConversationMessage(
    resolvedConversationId,
    message,
    token,
    imageData,
  );

  return { conversationId: resolvedConversationId, createdConversationId, reply };
}
