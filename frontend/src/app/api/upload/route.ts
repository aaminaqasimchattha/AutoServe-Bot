import { uploadCsvHandler } from '../../../handler/upload-csvHnadler';

export async function POST(request: Request) {
  return uploadCsvHandler(request);
}
