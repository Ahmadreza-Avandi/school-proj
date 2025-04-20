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

    // اعتبارسنجی ورودی‌های الزامی
    if (!fullName || !nationalCode || !phoneNumber || !password) {
      return res.status(400).json({ message: 'لطفا همه فیلدهای الزامی را پر کنید' });
    }

    try {
      // استفاده از آدرس داخلی داکر برای ارسال درخواست به سرویس Nest.js
      const nestApiUrl = process.env.NESTJS_API_URL || 'http://nestjs:3001';
      
      // لاگ کردن اطلاعات برای دیباگ
      console.log(`Sending user registration to: ${nestApiUrl}/users/add-user`);
      
      // ساخت داده‌های درخواست با فیلدهای اختیاری
      const requestData: any = {
        fullName,
        nationalCode,
        phoneNumber,
        password,
        roleId: roleId || 2, // تنظیم نقش به صورت پیشفرض 2 (کاربر عادی) اگر ارسال نشده باشد
      };

      // افزودن فیلدهای اختیاری در صورت وجود
      if (majorId !== undefined) requestData.majorId = Number(majorId);
      if (gradeId !== undefined) requestData.gradeId = Number(gradeId);
      if (identityPhoto) requestData.identityPhoto = identityPhoto;

      // نمایش داده‌های ارسالی به سرور
      console.log('Registration data:', JSON.stringify(requestData, null, 2));
      
      const response = await axios.post(
        `${nestApiUrl}/users/add-user`,
        requestData
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
