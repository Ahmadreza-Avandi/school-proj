import { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';

export default async (req: NextApiRequest, res: NextApiResponse) => {
  if (req.method === 'POST') {
    const { nationalCode, password } = req.body;

    try {
      // ارسال درخواست به API Nest.js برای ورود
      const loginResponse = await axios.post(
        'http://localhost:3001/auth/login',
        {
          nationalCode,
          password,
        }
      );
      const loginData = loginResponse.data as { access_token: string };

      // دریافت اطلاعات کاربر بعد از لاگین موفق
      try {
        const userResponse = await axios.get(
          `http://localhost:3001/users/by-national-code/${nationalCode}`,
          {
            headers: {
              Authorization: `Bearer ${loginData.access_token}`,
            },
          }
        );

        // ترکیب اطلاعات توکن و کاربر
        const responseData = {
          ...loginData,
          user: {
            roleId: userResponse.data.roleId,
            fullName: userResponse.data.fullName,
          },
        };

        // اگر ورود موفقیت‌آمیز بود
        res.status(200).json(responseData);
      } catch (userError) {
        // اگر دریافت اطلاعات کاربر با خطا مواجه شد، فقط توکن را برگردان
        res.status(200).json(loginData);
      }
    } catch (error) {
      // اگر ورود ناموفق بود
      res.status(400).json({ message: 'Invalid credentials' });
    }
  } else {
    res.status(405).json({ message: 'Method Not Allowed' });
  }
};
