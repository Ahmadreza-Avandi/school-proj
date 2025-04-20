import { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';

// Define environment variable type
declare global {
  namespace NodeJS {
    interface ProcessEnv {
      NESTJS_API_URL?: string;
    }
  }
}

export default async (req: NextApiRequest, res: NextApiResponse) => {
  if (req.method === 'POST') {
    const { fullName, nationalCode, phoneNumber, password, roleId, majorId, gradeId, identityPhoto } = req.body;

    // اعتبارسنجی ورودی‌ها
    if (!fullName || !nationalCode || !phoneNumber || !password || !roleId) {
      return res.status(400).json({ message: 'لطفا همه فیلدها را پر کنید' });
    }

    try {
      // استفاده از آدرس داخلی داکر برای ارسال درخواست به سرویس Nest.js
      const nestApiUrl = process.env.NESTJS_API_URL || 'http://nestjs:3001';
      
      // لاگ کردن اطلاعات برای دیباگ
      console.log(`Sending user registration to: ${nestApiUrl}/users`);
      
      const response = await axios.post(
        `${nestApiUrl}/users`,
        {
          fullName,
          nationalCode,
          phoneNumber,
          password,
          roleId,
          majorId, // افزودن رشته تحصیلی
          gradeId, // افزودن پایه تحصیلی
          identityPhoto, // افزودن تصویر شناسایی
        }
      );

      // اگر عملیات افزودن کاربر موفقیت‌آمیز بود
      return res.status(200).json(response.data);
    } catch (error: any) {
      // Handle errors with type checking
      console.error('Error adding user:', error);
      
      const errorMessage = error.response?.data?.message || 'Failed to add user';
      const statusCode = error.response?.status || 500;
      
      return res.status(statusCode).json({ message: errorMessage });
    }
  } else {
    return res.status(405).json({ message: 'Method Not Allowed' });
  }
};
